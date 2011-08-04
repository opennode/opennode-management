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
    cls = type(obj)

    interfaces = list(zope.interface.implementedBy(cls).interfaces())

    for base_cls in cls.__bases__:
        for interface in list(zope.interface.implementedBy(base_cls).interfaces()):
            interfaces.remove(interface)

    return interfaces
