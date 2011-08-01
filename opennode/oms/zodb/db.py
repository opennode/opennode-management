import functools
import inspect
import threading

import transaction
from ZEO.ClientStorage import ClientStorage
from ZODB import DB
from twisted.internet import reactor
from twisted.internet.threads import deferToThreadPool
from twisted.python.threadpool import ThreadPool
from twisted.python.threadable import isInIOThread

from opennode.oms.model.model import OmsRoot


__all__ = ['get_db', 'get_connection', 'get_root', 'transact', 'ref', 'deref']


_db = None
_threadpool = None
_connection = threading.local()


def init():
    global _db, _threadpool

    _threadpool = ThreadPool(minthreads=0, maxthreads=20)

    reactor.callWhenRunning(_threadpool.start)
    reactor.addSystemEventTrigger('during', 'shutdown', _threadpool.stop)

    storage = ClientStorage('db/socket')
    _db = DB(storage)

    init_schema()


def init_schema():
    root = get_root()

    if 'oms_root' not in root:
        root['oms_root'] = OmsRoot()
        transaction.commit()


def get_db():
    if not _db: init()
    if isInIOThread():
        raise Exception('The ZODB should not be accessed from the main thread')
    return _db


def get_connection():
    global _connection
    if not hasattr(_connection, 'x'):
        _connection.x = get_db().open()
    return _connection.x


def get_root():
    return get_connection().root()


def transact(fun):
    """Runs a callable inside a separate thread within a ZODB transaction.

    TODO: Add retry capability on ConflicErrors.

    """

    if not _db: init()

    # Verify that the wrapped callable has the required argument signature.
    arglist = inspect.getargspec(fun).args
    if not arglist or arglist[0] != 'self':
        raise TypeError("Only instance methods can be wrapped")

    def run_in_tx(fun, self, *args, **kwargs):
        try:
            result = fun(self, *args, **kwargs)
        except:
            transaction.abort()
            raise
        else:
            transaction.commit()
            return result

    @functools.wraps(fun)
    def wrapper(self, *args, **kwargs):
        return deferToThreadPool(reactor, _threadpool,
                                 lambda: run_in_tx(fun, self, *args, **kwargs))
    return wrapper


def ref(obj):
    return obj._p_oid


def deref(obj_id):
    assert isinstance(obj_id, str)
    return get_connection().get(obj_id)
