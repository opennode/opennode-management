import functools
import inspect
import random
import subprocess
import threading

import transaction
from ZEO.ClientStorage import ClientStorage
from twisted.internet import reactor, defer
from twisted.internet.threads import deferToThreadPool
from twisted.python import log
from twisted.python.threadable import isInIOThread
from twisted.python.threadpool import ThreadPool

from opennode.oms.config import get_config
from opennode.oms.model.model import OmsRoot


__all__ = ['get_db', 'get_connection', 'get_root', 'transact', 'ref', 'deref']


_db = None
_threadpool = None
_connection = threading.local()
_testing = False


class RollbackException(Exception):
    """Raised to cause a clean rollback of the transaction"""


class RollbackValue(object):
    def __init__(self, value):
        self.value = value


def init_threadpool():
    global _threadpool

    _threadpool = ThreadPool(minthreads=0, maxthreads=20)

    reactor.callWhenRunning(_threadpool.start)
    reactor.addSystemEventTrigger('during', 'shutdown', _threadpool.stop)


def get_db_dir():
    db_dir = 'db'
    try:
        # useful during development
        db_dir = subprocess.check_output('scripts/current_db_dir.sh').strip()
    except:
        pass

    if db_dir == 'db':
        db_dir = get_config().get('db', 'path')

    return db_dir


def init(test=False):
    global _db, _testing

    if not test:
        from ZODB import DB

        storage = ClientStorage('%s/socket' % get_db_dir())
        _db = DB(storage)
    else:
        from ZODB.tests.util import DB
        _db = DB()
        _testing = True

    init_schema()


def init_schema():
    root = get_root()

    if 'oms_root' not in root:
        root['oms_root'] = OmsRoot()
        transaction.commit()


def get_db():
    if not _db:
        init()
    if isInIOThread() and not _testing:
        raise Exception('The ZODB should not be accessed from the main thread')
    return _db


def get_connection():
    global _connection
    if not hasattr(_connection, 'x'):
        _connection.x = get_db().open()
    return _connection.x


def get_root():
    return get_connection().root()


def assert_transact(fun):
    """Used to decorate methods which assume to be running in a threadpool used for blocking io,
    for example those created by @db.transact.

    """

    @functools.wraps(fun)
    def wrapper(*args, **kwargs):
        if isInIOThread() and not _testing:
            log.msg('The ZODB should not be accessed from the main thread')
            raise Exception('The ZODB should not be accessed from the main thread')
        return fun(*args, **kwargs)
    return wrapper


def transact(fun):
    """Runs a callable inside a separate thread within a ZODB transaction.

    TODO: Add retry capability on ConflicErrors.

    """

    if not _threadpool:
        init_threadpool()

    def run_in_tx(fun, *args, **kwargs):
        if not _db:
            init()

        cfg = get_config()
        def trace(msg, t):
            ch = '/'
            if msg == "BEGINNING":
                ch = '\\'
            if cfg.getboolean('debug', 'trace_transactions', False):
                print "[transaction] %s\ttx:%s %s\tin %s from %s, line %s %s" % (msg, t.description, ch, fun, fun.__module__, inspect.getsourcelines(fun)[1], ch)

        try:
            t = transaction.begin()
            t.note("%s" % (random.randint(0, 1000000)))
            trace("BEGINNING", t)
            result = fun(*args, **kwargs)
        except RollbackException:
            transaction.abort()
        except:
            log.err("rolling back")
            trace("ABORTING", t)
            transaction.abort()
            raise
        else:
            if isinstance(result, RollbackValue):
                trace("V ROLLBACK", t)
                result = result.value
                transaction.abort()
            else:
                trace("COMMITTING", t)
                transaction.commit()

            return result

    @functools.wraps(fun)
    def wrapper(*args, **kwargs):
        if not _testing:
            return deferToThreadPool(reactor, _threadpool,
                                     lambda: run_in_tx(fun, *args, **kwargs))
        else:
            # No threading during testing
            return defer.succeed(run_in_tx(fun, *args, **kwargs))
    return wrapper


def ro_transact(fun):
    """Runs a callable inside a separate thread within a readonly ZODB transaction.

    Transaction is always rolledback.

    """

    if not _threadpool:
        init_threadpool()

    def run_in_tx(fun, *args, **kwargs):
        if not _db:
            init()

        try:
            transaction.begin()
            return fun(*args, **kwargs)
        finally:
            transaction.abort()

    @functools.wraps(fun)
    def wrapper(*args, **kwargs):
        if not _testing:
            return deferToThreadPool(reactor, _threadpool,
                                     lambda: run_in_tx(fun, *args, **kwargs))
        else:
            # No threading during testing
            return defer.succeed(run_in_tx(fun, *args, **kwargs))
    return wrapper


def ref(obj):
    return obj._p_oid


def deref(obj_id):
    assert isinstance(obj_id, str)
    return get_connection().get(obj_id)
