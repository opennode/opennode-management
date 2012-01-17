import functools
import inspect
import itertools
import re
import threading

import zope.interface
from zope.component import getSiteManager, implementedBy
from zope.interface import classImplements
from twisted.internet import defer, reactor


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


def blocking_yield(deferred):
    """This utility is part of the HDK (hack development toolkit) use with care and remove it's usage asap.

    Sometimes we have to synchronously wait for a deferred to complete,
    for example when executing inside db.transact code, which cannot 'yield'
    because currently db.transact doesn't handle returning a deferred.

    Or because we are running code inside a handler which cannot return a deferred
    otherwise we cannot block the caller or rollback the transaction in case of async code
    throwing exception (scenario: we want to prevent deletion of node)

    Use this utility only until you refactor the upstream code in order to use pure async code.
    """

    import time

    # install a failure handler, otherwise an unhandled deferred error will be logged
    failure = [None]

    @deferred
    def on_error(error):
        failure[0] = error

    while not deferred.called:
        time.sleep(0.1)

    if failure[0]:
        raise failure[0].value
    return deferred.result


def threaded(fun):
    """Helper decorator to quickly turn a function in a threaded function using a newly allocated thread,
    mostly useful during debugging/profiling in order to see if there are any queuing issues in the threadpools.

    """

    @functools.wraps(fun)
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=fun, args=args, kwargs=kwargs)
        thread.start()
    return wrapper


def trace(fun):
    @functools.wraps(fun)
    def wrapper(*args, **kwargs):
        print "[trace]", fun, args, kwargs
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


def exception_logger(fun):
    @functools.wraps(fun)
    def wrapper(*args, **kwargs):
        try:
            return fun(*args, **kwargs)
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise e
    return wrapper


def find_nth(haystack, needle, n, start_boundary=None):
    start = haystack.find(needle, start_boundary)
    while start >= 0 and n > 1:
        start = haystack.find(needle, start+len(needle))
        n -= 1
    return start
