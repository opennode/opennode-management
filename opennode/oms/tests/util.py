import inspect
import os
import sys
from Queue import Queue, Empty
from collections import namedtuple
from contextlib import contextmanager
from functools import wraps

from nose.twistedtools import threaded_reactor, stop_reactor

from opennode.oms.zodb import db
import time


_mayDelay = None

funcd_running = os.system("ps xa|grep [f]uncd >/dev/null") == 0


def run_in_reactor(fun):
    """Decorator for running tests in a Twisted reactor.

    Based on nose.twistedtools.deferred and is otherwise the same,
    except it expects the function to be blocking (ZODB access during
    testing is blocking/non-threaded).

    """

    if not inspect.isfunction(fun):
        global _mayDelay
        _mayDelay = max(_mayDelay, fun)
        return run_in_reactor

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


def teardown_reactor():
    stop_reactor()

def clean_db(fun):
    """Clean the test db before executing a given unit test.

    It can be also used to decorate the setUp() so that every test
    is ensured to run in a clean db, but you have to make sure setUp is also
    decorated with @run_in_reactor.

    """

    @wraps(fun)
    def wrapper(*args, **kwargs):
        # clean the db
        if hasattr(db._connection, 'x'):
            delattr(db._connection, 'x')
            db.init(test=True)
        return fun(*args, **kwargs)

    return wrapper


@contextmanager
def assert_not_raises():
    try:
        yield
    except Exception as e:
        raise AssertionError("No exception should have been raised but instead %s was raised" % repr(e))


def _pretty_print(name, args, kwargs):
    p_args = ', '.join(repr(arg) for arg in args)
    p_kwargs = ', '.join('%s=%s' % (key, repr(value)) for key, value in kwargs.items())
    p_all = [i for i in [p_args, p_kwargs] if i]
    return '%s(%s)' % (name, ', '.join(p_all))


class MethodProxy(object):
    def __init__(self, mock, name, index):
        self.mock = mock
        self.name = name
        self.index = index

    def __call__(self, *args, **kwargs):
        assert len(self.mock.method_calls) > self.index, \
               "Expected a %s call but instead there was no call" % _pretty_print(self.name, args, kwargs)

        call = self.mock.method_calls[self.index]

        def msg():
            return "Expected a %s call but found %s instead" % (_pretty_print(self.name, args, kwargs),
                                                                _pretty_print(*call))

        assert call[0] == self.name, msg()

        assert args == call[1], msg()

        assert kwargs == call[2], msg()


class MockProxy(object):
    def __init__(self, mock):
        self.mock = mock
        self.next_method_index = 0

    def __getattr__(self, name):
        ret = MethodProxy(self.__dict__['mock'], name, self.__dict__['next_method_index'])
        self.__dict__['next_method_index'] += 1
        return ret


class assert_mock(object):

    def __init__(self, mock):
        self.mock = mock

    def __enter__(self):
        self.proxy = MockProxy(self.mock)
        return self.proxy

    def __exit__(self, *exc_info):
        pass


def no_more_calls(mock_proxy):
    next_index = mock_proxy.__dict__['next_method_index']
    method_calls = mock_proxy.__dict__['mock'].method_calls
    assert next_index == len(method_calls), \
           "There should be no more method calls but there are: %s" % '; '.join(_pretty_print(*call) for call in method_calls)


def skip(mock_proxy, num):
    calls_left = len(mock_proxy.__dict__['mock'].method_calls) - mock_proxy.__dict__['next_method_index']
    if calls_left < num:
        raise AssertionError("There should be at least %s more method calls but there are only %s" % (num, calls_left))
    mock_proxy.__dict__['next_method_index'] += num


class CallDescr(namedtuple('CallDescrBase', ('name', 'args', 'kwargs', 'mock_proxy'))):
    """Describes a method call.

    Also behaves as a context manager for use with the Python `with`
    statement.  When used as a context manager, automatically `skip`s
    to the next method call after the `with` block.

    """

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        skip(self.mock_proxy, 1)

    @property
    def arg(self):
        assert len(self.args) == 1, "Call should only have a single argument"
        return self.args[0]


def current_call(mock_proxy):
    """Returns the descriptor about the next method call that would be asserted against.

    When not called inside a `with` statement, care needs to be take
    to manually `skip` to the next method call as needed.

    """
    next_method_ix = mock_proxy.__dict__['next_method_index']
    call = mock_proxy.__dict__['mock'].method_calls[next_method_ix]
    return CallDescr(*call, mock_proxy=mock_proxy)
