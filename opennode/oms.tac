#!/usr/bin/env twistd -ny
import functools
import logging
import logging.config
import errno
import os
import Queue

from twisted.application import service, internet
from twisted.conch.insults import insults
from twisted.conch.manhole_ssh import ConchFactory
from twisted.cred import portal
from twisted.internet import reactor, defer
from twisted.python import log
from twisted.web import server
from zope.component import handle

from opennode.oms.config import get_config
from opennode.oms.core import setup_environ, AfterApplicationInitalizedEvent
from opennode.oms.logging import FilteredPythonLoggingObserver


def create_http_server():
    from opennode.oms.endpoint.httprest.root import HttpRestServer

    rest_server = HttpRestServer(avatar=None)
    site = server.Site(resource=rest_server)
    tcp_server = internet.TCPServer(get_config().getint('rest', 'port'), site)

    return tcp_server


def create_ssh_server():
    from opennode.oms.endpoint.ssh.protocol import OmsShellProtocol
    from opennode.oms.endpoint.ssh.session import OmsTerminalRealm
    from opennode.oms.security.authentication import checkers

    def chainProtocolFactory():
        return insults.ServerProtocol(OmsShellProtocol)

    the_portal = portal.Portal(OmsTerminalRealm())

    for ch in checkers():
        the_portal.registerChecker(ch)

    conch_factory = ConchFactory(the_portal)
    ssh_server = internet.TCPServer(get_config().getint('ssh', 'port'), conch_factory)

    return ssh_server


def create_application():
    setup_environ()

    application = service.Application("OpenNode Management Service")

    create_http_server().setServiceParent(application)
    create_ssh_server().setServiceParent(application)
    # TODO: create_websocket_server().setServiceParent(application)

    def after_startup():
        handle(AfterApplicationInitalizedEvent())
    reactor.addSystemEventTrigger('after', 'startup', after_startup)
    # increase a suggested thread pool to reduce the risk of pool depletion
    # caused by multiple simultaneous commands
    reactor.suggestThreadPoolSize(100)

    return application


# 10k records is ought to be enough for anyone!
global_op_queue = Queue.Queue(10000)

def put_to_queue(data):
    global global_op_queue
    try:
        global_op_queue.put(data, False)
    except Queue.Full:
        try:
            global_op_queue.get(False)
        except Queue.Empty:
            pass
        put_to_queue(data)


def dump_queue(fd):
    global global_op_queue
    while not global_op_queue.empty():
        record = global_op_queue.get()
        if record[1] == fd:
            log.msg('%s %s s: %s\n                                           %s'
                    % record, system='epoll')
        else:
            log.msg('             %s %s s: %s'
                    '\n                                      %s'
                    % record, system='epoll')


def monkey_patch_epollreactor():
    def add_wrapper(_addw):
        @functools.wraps(_addw)
        def _add_substitute(xer, primary, other, selectables, event, aevent):
            try:
                fd = xer.fileno()
                if fd not in primary:
                    if fd in other:
                        put_to_queue(('&&&', fd, len(selectables), xer))
                    else:
                        put_to_queue(('+++', fd, len(selectables), xer))
                _addw(xer, primary, other, selectables, event, aevent)
            except IOError as e:
                if e.errno == errno.ENOENT:
                    if fd in other:
                        del other[fd]
                    log.msg('WARNING: It appears like %s is not registered, '
                            'although it should be. other: %s %s' % (fd, other, xer),
                            system='epoll-add')
                    log.msg('Dump of last few operations follows... '
                            '+++ - reg, --- - unreg, &&& - modify', system='epoll-add')
                    dump_queue(fd)
                    log.msg('Retrying _add recursively...', system='epoll-add')
                    _addw(xer, primary, other, selectables, event, aevent)
                else:
                    raise
        return _add_substitute

    def remove_wrapper(_removew):
        @functools.wraps(_removew)
        def _remove_substitute(xer, primary, other, selectables, event, aevent):
            try:
                fd = xer.fileno()
                if fd in primary:
                    if fd in other:
                        put_to_queue(('&&&', fd, len(selectables), xer))
                    else:
                        put_to_queue(('---', fd, len(selectables), xer))
                _removew(xer, primary, other, selectables, event, aevent)
            except IOError as e:
                if e.errno == errno.ENOENT:
                    if fd in other:
                        del other[fd]
                    log.msg('WARNING: It appears like %s is not registered, '
                            'although it should be. other: %s %s' % (fd, other, xer),
                            system='epoll-remove')
                    log.msg('Dump of last few operations follows... '
                            '+++ - reg, --- - unreg, &&& - modify', system='epoll-remove')
                    dump_queue()
                    log.msg('Retrying _remove recursively...', system='epoll-remove')
                    _removew(xer, primary, other, selectables, event, aevent)
                else:
                    raise
        return _remove_substitute

    reactor._add = add_wrapper(reactor._add)
    reactor._remove = remove_wrapper(reactor._remove)


monkey_patch_epollreactor()

defer.Deferred.debug = get_config().getboolean('debug', 'deferred_debug', False)

def setup_logging():
    log_filename = get_config().get('logging', 'file')
    log_level = get_config().getstring('logging', 'level', 'INFO')
    logging.config.dictConfig({
        'formatters': {
            'default': {'format': '%(asctime)s %(thread)x %(name)s %(levelname)s %(message)s',},
            'twisted': {'format': '%(asctime)s %(thread)x %(name)s %(levelname)s %(system)s %(message)s',}},
        'handlers': {'default': {'class': 'logging.FileHandler', 'filename': log_filename,
                                     'formatter': 'default'},
                     'twisted': {'class': 'logging.FileHandler', 'filename': log_filename,
                                 'formatter': 'twisted'},},
        'root': {'handlers': ['default'], 'level': log_level},
        'loggers': {'twisted': {'level': 'INFO', 'handlers': ['twisted'], 'propagate': False},
                    'txn': {'level': 'WARNING'},
                    'ZEO.zrpc': {'level': 'WARNING'},
                    'ZEO.ClientStorage': {'level': 'WARNING',},
                   },
        'version': 1,
        'disable_existing_loggers': False
    })
    if os.path.exists('logging.conf'):
        logging.config.fileConfig('logging.conf', disable_existing_loggers=False)
    logging.warn('Logging level is set to %s' %
                 logging.getLevelName(logging.getLogger('root').getEffectiveLevel()))
    observer = FilteredPythonLoggingObserver()
    return observer.emit

logger = setup_logging()
application = create_application()
application.setComponent(log.ILogObserver, logger)
