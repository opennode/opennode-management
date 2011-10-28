import zope.interface


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


class Singleton(type):
    """Singleton metaclass."""

    def __init__(cls, name, bases, dict):
        super(Singleton, cls).__init__(name, bases, dict)
        cls.instance = None

    def __call__(cls,*args,**kw):
        if cls.instance is None:
            cls.instance = super(Singleton, cls).__call__(*args, **kw)
        return cls.instance
