import sys
from Queue import Queue, Empty
from functools import wraps

from nose.twistedtools import threaded_reactor


def run_in_reactor(fun):
    """Decorator for running tests in a Twisted reactor.

    Based on nose.twistedtools.deferred and is otherwise the same,
    except it expects the function to be blocking (ZODB access during
    testing is blocking/non-threaded).

    """

    @wraps(fun)
    def wrapper(*args, **kwargs):
        reactor, reactor_thread = threaded_reactor()
        if reactor is None:
            raise ImportError("twisted is not available or could not be imported")
        q = Queue()
        def g():
            try:
                fun(*args, **kwargs)
            except:
                q.put(sys.exc_info())
            else:
                q.put(None)
        reactor.callFromThread(g)
        try:
            error = q.get(timeout=10)
        except Empty:
            raise RuntimeError('Timeout expired')

        if error is not None:
            exc_type, exc_value, tb = error
            raise exc_type, exc_value, tb

    return wrapper
