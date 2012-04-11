import functools
import inspect
import random
import subprocess
import threading
import time
import transaction

from ZEO.ClientStorage import ClientStorage
from ZODB.FileStorage import FileStorage
from ZODB.POSException import ConflictError, ReadConflictError
from grokcore.component import subscribe
from twisted.internet import reactor, defer
from twisted.internet.threads import deferToThreadPool
from twisted.python import log
from twisted.python.threadable import isInIOThread
from twisted.python.threadpool import ThreadPool
from zope.component import handle
from zope.interface import Interface, implements

from opennode.oms.config import get_config
from opennode.oms.core import IBeforeApplicationInitializedEvent
from opennode.oms.model.model import OmsRoot
from opennode.oms.zodb.proxy import make_persistent_proxy


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


class IBeforeDatabaseInitializedEvent(Interface):
    """Emitted before database is initialized"""


class BeforeDatabaseInitalizedEvent(object):
    implements(IBeforeDatabaseInitializedEvent)


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


@subscribe(IBeforeApplicationInitializedEvent)
def initialize_database(event):
    init()


def init(test=False):
    global _db, _testing

    if _db and not test:
        return

    print "[db] Initializing zodb"
    handle(BeforeDatabaseInitalizedEvent())

    if not test:
        storage_type = get_config().get('db', 'storage_type')

        if storage_type == 'zeo':
            from ZODB import DB

            storage = ClientStorage('%s/socket' % get_db_dir())
            _db = DB(storage)
        elif storage_type == 'embedded':
            from ZODB import DB

            storage = FileStorage('%s/data.fs' % get_db_dir())
            _db = DB(storage)
        elif storage_type == 'memory':
            from ZODB.tests.util import DB

            _db = DB()
        else:
            raise Exception("Unknown storage type '%s'" % storage_type)
    else:
        from ZODB.tests.util import DB
        _db = DB()
        _testing = True

    init_schema()


def init_schema():
    root = get_root(True)

    if 'oms_root' not in root:
        root['oms_root'] = OmsRoot()
        transaction.commit()


def get_db():
    if not _db:
        raise Exception('DB not initalized')
    if isInIOThread() and not _testing:
        raise Exception('The ZODB should not be accessed from the main thread')
    return _db


def get_connection(accept_main_thread=False):
    if not accept_main_thread and isInIOThread() and not _testing:
        raise Exception('The ZODB should not be accessed from the main thread')

    global _connection
    if not hasattr(_connection, 'x'):
        _connection.x = get_db().open()
    return _connection.x


def get_root(accept_main_thread=False):
    return get_connection(accept_main_thread).root()


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

    Returned values are deeply copied. Currently only zodb objects returned directly or
    contained in the first level content of lists/sets/dicts are copied.
    """

    if not _threadpool:
        init_threadpool()

    def run_in_tx(fun, *args, **kwargs):
        if not _db:
            raise Exception('DB not initalized')

        cfg = get_config()
        def trace(msg, t):
            ch = '/'
            if msg == "BEGINNING":
                ch = '\\'
            if cfg.getboolean('debug', 'trace_transactions', False):
                print "[transaction] %s\ttx:%s %s\tin %s from %s, line %s %s" % (msg, t.description, ch, fun, fun.__module__, inspect.getsourcelines(fun)[1], ch)

        retries = cfg.getint('db', 'conflict_retries')

        retrying = False
        for i in xrange(0, retries + 1):
            try:
                t = transaction.begin()
                t.note("%s" % (random.randint(0, 1000000)))
                trace("BEGINNING", t)
                result = fun(*args, **kwargs)
            except RollbackException:
                transaction.abort()
                return
            except:
                log.err("rolling back")
                trace("ABORTING", t)
                transaction.abort()
                raise
            else:
                try:
                    if isinstance(result, RollbackValue):
                        trace("V ROLLBACK", t)
                        result = result.value
                        transaction.abort()
                    else:
                        trace("COMMITTING", t)
                        transaction.commit()
                        if retrying:
                            trace("SUCCEEDED COMMITTING, AFTER %s attempts" % i, t)

                    return make_persistent_proxy(result)
                except ReadConflictError as e:
                    trace("GOT READ CONFLICT IN RW TRANASCT, retrying %s" % i, t)
                    retrying = True
                    time.sleep(random.random()*0.1)
                except ConflictError as e:
                    trace("GOT WRITE CONFLICT IN RW TRANASCT, retrying %s" % i, t)
                    retrying = True
                    time.sleep(random.random()*0.1)
        raise e

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

    Returned values are deeply copied. Currently only zodb objects returned directly or
    contained in the first level content of lists/sets/dicts are copied.

    """

    if not _threadpool:
        init_threadpool()

    def run_in_tx(fun, *args, **kwargs):
        if not _db:
            raise Exception('DB not initalized')

        try:
            transaction.begin()
            return make_persistent_proxy(fun(*args, **kwargs))
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


def get(obj, name):
    return ro_transact(lambda: getattr(obj, name))()
