import inspect
import sqlite3
from collections import namedtuple
from functools import wraps

#~ from storm.twisted.transact import Transactor
from storm.zope.interfaces import IZStorm
from storm.zope.zstorm import ZStorm
from twisted.internet import reactor
from twisted.python.threadpool import ThreadPool
from zope.component import getUtility, provideUtility

from opennode.oms.db.storm_twisted import Transactor


__all__ = ['transact', 'ensure_transaction', 'get_store', 'ref', 'deref']


# TODO: Move this to an external, locally overridable configuration file/module.
DB_NAME = 'oms.db'
DB_URI = 'sqlite:%s' % DB_NAME

sqlite3.enable_callback_tracebacks(True)


# The global Transactor instance used when executing DB transactions:
transactor = None


def init():
    """Initialises the thread pool and Transactor used for executing
    DB transactions.

    """
    zstorm = ZStorm()
    zstorm.set_default_uri('main', DB_URI)

    provideUtility(zstorm)

    threadpool = ThreadPool(minthreads=0, maxthreads=10)

    reactor.callWhenRunning(threadpool.start)
    reactor.addSystemEventTrigger('during', 'shutdown', threadpool.stop)

    global transactor
    transactor = Transactor(threadpool)


def transact(fun):
    """Marks a method as runnable inside a Storm transaction.

    Methods marked with this decorator are deferred to a thread pool
    and executed in the context of a global Storm ORM Transactor
    object. No ORM objects should be returned from the method.

    """

    # Verify that the wrapped callable has the required argument signature.
    arglist = inspect.getargspec(fun).args
    if not arglist or arglist[0] != 'self':
        raise TypeError("Only instance methods can be wrapped")

    global transactor
    if not transactor: init()

    @wraps(fun)
    def wrapper(self, *args, **kwargs):
        return transactor.run(fun, self, *args, **kwargs)
    return wrapper


def ensure_transaction(fun):
    """Ensures that there is a running transaction (which has been
    started by Transactor.run) in the current thread, and
    (optionally?) starts one if not.

    *Not implemented!*

    """
    # TODO: Check if there is a transaction currently running.
    return fun


def get_store():
    """An convenience alias for zope.component.getUtility(IZStorm).get('main')."""
    if not transactor: init()
    return getUtility(IZStorm).get('main')


class Ref(namedtuple('Ref', ['cls', 'id'])):
    """Represents a reference to a DB backed model object.

    The reason this is needed is because the Storm ORM forbids passing
    of DB backed objects outside of thread boundaries for thread
    safety.

    Stores the class and the ID of the referenced object.

    """

    def __str__(self):
        return 'Ref[%s:%s]' % (self.cls.__name__, self.id)


def deref(obj_or_ref):
    """Dereferences a reference to a DB backed Storm ORM object.

    If passed a non-reference, simply returns it. This is useful when
    dealing with model objects that are not DB backed and do not need
    to be stored as references.

    """
    if isinstance(obj_or_ref, Ref):
        ref = obj_or_ref
        assert hasattr(ref.cls, '__storm_table__')
        obj = get_store().get(ref.cls, ref.id)
    else:
        obj = obj_or_ref
    return obj


def ref(obj):
    """Creates a thread safe reference to a DB backed Storm ORM object.

    If the passed in object is not a Storm backed model object,
    returns the object. This is useful when dealing with model objects
    that are not DB backed and do not need to be stored as references.

    """
    if hasattr(obj, '__storm_table__'):
        return Ref(type(obj), obj.id)
    else:
        return obj
