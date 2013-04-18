import functools
import inspect
import time
import threading

from Queue import Queue, Empty

import zope.interface
from zope.component import getSiteManager, implementedBy
from zope.interface import classImplements
from twisted.internet import defer, reactor
from twisted.python import log
from twisted.python.failure import Failure

from opennode.oms.config import get_config


def get_direct_interfaces(obj):
    """Returns the interfaces that the parent class of `obj`
    implements, exluding any that any of its ancestor classes
    implement.

    >>> from zope.interface import Interface, implements, implementedBy
    >>> class IA(Interface): pass
    >>> class IB(Interface): pass
    >>> class A: implements(IA)
    >>> class B(A): implements(IB)
    >>> b = B()
    >>> [i.__name__ for i in list(implementedBy(B).interfaces())]
    ['IB', 'IA']
    >>> [i.__name__ for i in get_direct_interfaces(b)]
    ['IB']

    """
    cls = obj if isinstance(obj, type) else type(obj)

    if not isinstance(obj, type) and hasattr(obj, 'implemented_interfaces'):
        interfaces = obj.implemented_interfaces()
    else:
        interfaces = list(zope.interface.implementedBy(cls).interfaces())

    for base_cls in cls.__bases__:
        for interface in list(zope.interface.implementedBy(base_cls).interfaces()):
            # in multiple inheritance this it could be already removed
            if interface in interfaces:
                interfaces.remove(interface)

    return interfaces


def get_direct_interface(obj):
    interfaces = get_direct_interfaces(obj)
    if not interfaces:
        return None
    if len(interfaces) == 1:
        return interfaces[0]
    else:
        raise Exception("Object implements more than 1 interface")


def query_adapter_for_class(cls, interface):
    return getSiteManager().adapters.lookup([implementedBy(cls)], interface)


class Singleton(type):
    """Singleton metaclass."""

    def __init__(cls, name, bases, dict):
        super(Singleton, cls).__init__(name, bases, dict)
        cls.instance = None

    def __call__(cls, *args, **kw):
        if cls.instance is None:
            cls.instance = super(Singleton, cls).__call__(*args, **kw)
        return cls.instance


def subscription_factory(cls, *args, **kwargs):
    """Utility which allows to to quickly register a subscription adapters which returns new instantiated objects
    of a given class

    >>> provideSubscriptionAdapter(subscription_factory(MetricsDaemonProcess), adapts=(IProc,))

    """

    class SubscriptionFactoryWrapper(object):
        def __new__(self, *_ignore):
            return cls(*args)

    interfaces = get_direct_interfaces(cls)
    classImplements(SubscriptionFactoryWrapper, *interfaces)
    return SubscriptionFactoryWrapper


def adapter_value(value):
    """Utility which allows to to quickly register a subscription adapter  as a value instead of

    >>> provideSubscriptionAdapter(adapter_value(['useful', 'stuff']), adapts=(Compute,), provides=ISomething)

    """

    def wrapper(*_):
        return value
    return wrapper


def async_sleep(secs):
    """Util which helps writing synchronous looking code with
    defer.inlineCallbacks.

    Returns a deferred which is triggered after `secs` seconds.

    """

    d = defer.Deferred()
    reactor.callLater(secs, d.callback, None)
    return d


def blocking_yield(deferred, timeout=None):
    """This utility is part of the HDK (hack development toolkit) use with care and remove its usage asap.

    Sometimes we have to synchronously wait for a deferred to complete,
    for example when executing inside db.transact code, which cannot 'yield'
    because currently db.transact doesn't handle returning a deferred.

    Or because we are running code inside a handler which cannot return a deferred
    otherwise we cannot block the caller or rollback the transaction in case of async code
    throwing exception (scenario: we want to prevent deletion of node)

    Use this utility only until you refactor the upstream code in order to use pure async code.
    """

    q = Queue()
    deferred.addBoth(q.put)
    try:
        ret = q.get(True, timeout or 100)
    except Empty:
        raise defer.TimeoutError
    if isinstance(ret, Failure):
        ret.raiseException()
    else:
        return ret


def threaded(fun):
    """Helper decorator to quickly turn a function in a threaded function using a newly allocated thread,
    mostly useful during debugging/profiling in order to see if there are any queuing issues in the
    threadpools.

    """

    @functools.wraps(fun)
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=fun, args=args, kwargs=kwargs)
        thread.start()
    return wrapper


def trace(fun):
    @functools.wraps(fun)
    def wrapper(*args, **kwargs):
        log.msg('%s %s %s' % (fun, args, kwargs), system='trace')
        return fun(*args, **kwargs)
    return wrapper


def trace_methods(cls):
    def trace_method(name):
        fun = getattr(cls, name)
        if inspect.ismethod(fun):
            setattr(cls, name, trace(fun))

    for name in cls.__dict__:
        trace_method(name)


def get_u(obj, key):
    val = obj.get(key)
    return unicode(val) if val is not None else None


def get_i(obj, key):
    val = obj.get(key)
    return int(val) if val is not None else None


def get_f(obj, key):
    val = obj.get(key)
    return float(val) if val is not None else None


def exception_logger(fun):
    @functools.wraps(fun)
    def wrapper(*args, **kwargs):
        try:
            res = fun(*args, **kwargs)
            if isinstance(res, defer.Deferred):
                @res
                def on_error(failure):
                    log.msg("Got unhandled exception: %s" % failure.getErrorMessage(), system='debug')
                    if get_config().getboolean('debug', 'print_exceptions'):
                        log.err(failure, system='debug')
            return res
        except Exception:
            if get_config().getboolean('debug', 'print_exceptions'):
                log.err(system='debug')
            raise
    return wrapper


def find_nth(haystack, needle, n, start_boundary=None):
    start = haystack.find(needle, start_boundary)
    while start >= 0 and n > 1:
        start = haystack.find(needle, start + len(needle))
        n -= 1
    return start


class benchmark(object):
    """Can be used either as decorator:
    >>> class Foo(object):
    ...   @benchmark("some description")
    ...   def doit(self, args):
    ...      # your code


    or as context manager:
    >>> with benchmark("some description"):
    >>>    # your code

    and it will print out the time spent in the function or block.
    """

    def __init__(self, name):
        self.name = name

    def __call__(self, fun):
        @functools.wraps(fun)
        def wrapper(*args, **kwargs):
            with self:
                return fun(*args, **kwargs)
        return wrapper

    def __enter__(self):
        self.start = time.time()

    def __exit__(self, ty, val, tb):
        end = time.time()
        print("%s : %0.3f seconds" % (self.name, end - self.start))
        return False


class TimeoutException(Exception):
    """Raised when time expires in timeout decorator"""


def timeout(secs):
    """
    Decorator to add timeout to Deferred calls
    """
    def wrap(func):
        @defer.inlineCallbacks
        @functools.wraps(func)
        def _timeout(*args, **kwargs):
            rawD = func(*args, **kwargs)
            if not isinstance(rawD, defer.Deferred):
                defer.returnValue(rawD)

            timeoutD = defer.Deferred()
            timesUp = reactor.callLater(secs, timeoutD.callback, None)

            try:
                rawResult, timeoutResult = yield defer.DeferredList([rawD, timeoutD],
                                                                    fireOnOneCallback=True,
                                                                    fireOnOneErrback=True,
                                                                    consumeErrors=True)
            except defer.FirstError, e:
                #Only rawD should raise an exception
                assert e.index == 0
                timesUp.cancel()
                e.subFailure.raiseException()
            else:
                #Timeout
                if timeoutD.called:
                    rawD.cancel()
                    raise TimeoutException("%s secs have expired" % secs)

            #No timeout
            timesUp.cancel()
            defer.returnValue(rawResult)
        return _timeout
    return wrap
