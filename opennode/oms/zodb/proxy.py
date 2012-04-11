# adapted from generic python proxy code available at http://code.activestate.com/recipes/252151-generalized-delegates-and-proxies/
# credit to Goncalo Rodrigues on Tue, 18 Nov 2003 (PSF)


from twisted.python.threadable import isInIOThread
from twisted.internet import defer

from opennode.oms.config import get_config


__all__ = ['PersistentProxy', 'make_persistent_proxy']


def make_persistent_proxy(res):
    import inspect
    if res is None:
        return None
    if isinstance(res, type):
        return res
    if isinstance(res, basestring) or isinstance(res, int) or isinstance(res, float) or isinstance(res, defer.Deferred):
        return res
    if inspect.isroutine(res) or res.__class__ == ([].__str__).__class__:
        return CallableViralProxy(res)
    return PersistentProxy(res)


def forbidden_outside_transaction(self, name):
    return name not in ['__class__', '__providedBy__', '__implements__', '__conform__'] and hasattr(object.__getattribute__(self, "_obj"), '_p_jar')


def ensure_fixed_up(self, name, op):
    from opennode.oms.zodb.db import ref, deref

    if not forbidden_outside_transaction(self, name):
        return

    if isInIOThread():
        msg = "Cannot %s '%s' attribute from persistent proxy object '%s' while in the main thread" % (op, name, self)
        if get_config().getboolean('debug', 'print_exceptions'):
            print msg
            import traceback
            traceback.print_stack()
        raise Exception(msg)

    oid = ref(object.__getattribute__(self, "_obj"))
    if oid is not None:
        new_obj = deref(oid)
        object.__setattr__(self, "_obj", new_obj)

    object.__setattr__(self, "_fixed_up", True)


class PersistentProxy(object):
    """This is a proxy object which tracks attribute acces when the persistent object is outsite a living transaction
    (e.g. when returned from a db.transact deferred).
    The access will cause an exception if it's done in the main thread.
    Access done in a zodb thread will cause the object to be reloaded in the current transaction.

    """

    __slots__ = ["_obj", "__weakref__"]
    def __init__(self, obj):
        object.__setattr__(self, "_obj", obj)
        object.__setattr__(self, "_fixed_up", False)

    #
    # proxying (special cases)
    #
    def __getattribute__(self, name):
        ensure_fixed_up(self, name, 'read')

        res = getattr(object.__getattribute__(self, "_obj"), name)
        if name not in ['__providedBy__']:
            return make_persistent_proxy(res)
        return res

    def __delattr__(self, name):
        delattr(object.__getattribute__(self, "_obj"), name)
    def __setattr__(self, name, value):
        ensure_fixed_up(self, name, 'write')

        setattr(object.__getattribute__(self, "_obj"), name, value)

    def __nonzero__(self):
        return bool(object.__getattribute__(self, "_obj"))
    def __str__(self):
        return str(object.__getattribute__(self, "_obj"))
    def __repr__(self):
        return repr(object.__getattribute__(self, "_obj"))

    #
    # factories
    #
    _special_names = [
        '__abs__', '__add__', '__and__', '__call__', '__cmp__', '__coerce__',
        '__contains__', '__delitem__', '__delslice__', '__div__', '__divmod__',
        '__eq__', '__float__', '__floordiv__', '__ge__', '__getitem__',
        '__getslice__', '__gt__', '__hash__', '__hex__', '__iadd__', '__iand__',
        '__idiv__', '__idivmod__', '__ifloordiv__', '__ilshift__', '__imod__',
        '__imul__', '__int__', '__invert__', '__ior__', '__ipow__', '__irshift__',
        '__isub__', '__iter__', '__itruediv__', '__ixor__', '__le__', '__len__',
        '__long__', '__lshift__', '__lt__', '__mod__', '__mul__', '__ne__',
        '__neg__', '__oct__', '__or__', '__pos__', '__pow__', '__radd__',
        '__rand__', '__rdiv__', '__rdivmod__', '__reduce__', '__reduce_ex__',
        '__repr__', '__reversed__', '__rfloorfiv__', '__rlshift__', '__rmod__',
        '__rmul__', '__ror__', '__rpow__', '__rrshift__', '__rshift__', '__rsub__',
        '__rtruediv__', '__rxor__', '__setitem__', '__setslice__', '__sub__',
        '__truediv__', '__xor__', 'next',
    ]

    _proxied_specials = ['__iter__', 'next']

    @classmethod
    def _create_class_proxy(cls, theclass):
        """creates a proxy for the given class"""

        def make_method(name):
            def method(self, *args, **kw):
                res = getattr(object.__getattribute__(self, "_obj"), name)(*args, **kw)
                if name in cls._proxied_specials:
                    return make_persistent_proxy(res)
                return res
            return method

        namespace = {}
        for name in cls._special_names:
            if name in dir(theclass):
                namespace[name] = make_method(name)
        return type("%s(%s)" % (cls.__name__, theclass.__name__), (cls,), namespace)

    def __new__(cls, obj, *args, **kwargs):
        """
        creates an proxy instance referencing `obj`. (obj, *args, **kwargs) are
        passed to this class' __init__, so deriving classes can define an
        __init__ method of their own.
        note: _class_proxy_cache is unique per deriving class (each deriving
        class must hold its own cache)
        """
        try:
            cache = cls.__dict__["_class_proxy_cache"]
        except KeyError:
            cls._class_proxy_cache = cache = {}
        try:
            theclass = cache[obj.__class__]
        except KeyError:
            cache[obj.__class__] = theclass = cls._create_class_proxy(obj.__class__)
        ins = object.__new__(theclass)
        theclass.__init__(ins, obj, *args, **kwargs)
        return ins


class CallableViralProxy(PersistentProxy):
    def __init__(self, obj):
        object.__setattr__(self, "_obj", obj)

    def __call__(self, *args, **kwargs):
        return make_persistent_proxy(object.__getattribute__(self, "_obj")(*args, **kwargs))
