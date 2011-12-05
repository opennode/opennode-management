from nose.tools import assert_raises
from zope.interface import Interface, classImplements

from opennode.oms.util import get_direct_interfaces, get_direct_interface


class IDirect(Interface):
    pass


class IDirect2(IDirect):
    pass


def test_basic():
    assert_direct_interfaces(type(None), [], instance=None)
    assert_direct_interfaces(object, [])

    class Foo(object):
        pass
    assert_direct_interfaces(Foo, [])

    classImplements(Foo, IDirect)
    assert_direct_interfaces(Foo, [IDirect])

    class Bar(Foo):
        pass
    assert_direct_interfaces(Bar, [])

    classImplements(Foo, IDirect2)
    assert_direct_interfaces(Foo, [IDirect, IDirect2])

    assert_direct_interfaces(Bar, [])

    # If a parent class already implements an interface, but it's also
    # a direct interface, it still won't be returned.  This case is
    # not handled as it's simply not needed and unlikely.
    classImplements(Bar, IDirect)
    assert_direct_interfaces(Bar, [])


NONE = object()


def assert_direct_interfaces(cls, interfaces, instance=NONE):
    if instance is NONE:
        instance = cls()
    for i in (cls, instance):
        direct_interfaces = get_direct_interfaces(i)
        assert interfaces == direct_interfaces, \
               "%s should have no direct interfaces" % i
        if len(interfaces) <= 1:
            direct_interface = get_direct_interface(i)
            assert (interfaces[0] if interfaces else None) == direct_interface, \
                   "%s should not have a direct interface" % i
        else:
            with assert_raises(Exception) as cm:
                get_direct_interface(i)
            assert cm.exception.args == ("Object implements more than 1 interface", )
