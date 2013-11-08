#!/usr/bin/env twistd -ny

from twisted.application import service, internet
from twisted.conch.insults import insults
from twisted.conch.manhole_ssh import ConchFactory
from twisted.cred import portal
from twisted.internet import reactor, defer
from twisted.python import log
from twisted.web import server
from zope.component import handle

from opennode.__mpatches import monkey_patch_epollreactor
from opennode.oms.config import get_config
from opennode.oms.core import setup_environ, AfterApplicationInitalizedEvent
from opennode.oms.log import setup_logging


def create_http_server():
    from opennode.oms.endpoint.httprest.root import HttpRestServer

    rest_server = HttpRestServer(avatar=None)
    site = server.Site(resource=rest_server)
    tcp_server = internet.TCPServer(get_config().getint('rest', 'port'), site,
                                    interface=get_config().getstring('rest', 'interface', ''))

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
    ssh_server = internet.TCPServer(get_config().getint('ssh', 'port'), conch_factory,
                                    interface=get_config().getstring('ssh', 'interface', ''))

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

if get_config().getboolean('debug', 'debug_epollreactor', False):
    monkey_patch_epollreactor()

defer.Deferred.debug = get_config().getboolean('debug', 'deferred_debug', False)
logger = setup_logging()
application = create_application()
application.setComponent(log.ILogObserver, logger)
