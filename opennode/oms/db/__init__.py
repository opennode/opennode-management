import inspect
import sqlite3
from functools import wraps

#~ from storm.twisted.transact import Transactor
from storm.zope.interfaces import IZStorm
from storm.zope.zstorm import ZStorm
from twisted.internet import reactor
from twisted.python.threadpool import ThreadPool
from zope.component import getUtility, provideUtility

from opennode.oms.db.storm_twisted import Transactor


__all__ = ['transact']


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

    Passes a thread local Storm store instance as the first non-self
    argument, which must be called 'store'.

    Methods marked with this decorator are deferred to a thread pool
    and executed in the context of a global Storm ORM Transactor
    object. No ORM objects should be returned from the method.

    """

    # Verify that the wrapped callable has the required argument signature.
    arglist = inspect.getargspec(fun).args
    if not arglist or arglist[0] != 'self':
        raise TypeError("Only instance methods can be wrapped")
    elif len(arglist) < 2 or arglist[1] != 'store':
        raise TypeError("Wrapped methods must take 'store' as the first argument after 'self'")

    global transactor
    if not transactor: init()

    @wraps(fun)
    def wrapper(self, *args, **kwargs):
        def inner(self, *args, **kwargs):
            zstorm = getUtility(IZStorm)
            store = zstorm.get('main')
            return fun(self, store, *args, **kwargs)
        return transactor.run(inner, self, *args, **kwargs)
    return wrapper
