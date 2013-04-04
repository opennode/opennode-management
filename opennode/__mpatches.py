import functools
import errno
import Queue

from twisted.python import log
from twisted.internet import reactor

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
