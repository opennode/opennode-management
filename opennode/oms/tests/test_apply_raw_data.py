from nose.tools import assert_raises
from zope import schema
from zope.component import adapter, provideHandler
from zope.interface import Interface, implements

from opennode.oms.model.form import RawDataApplier, RawDataValidatingFactory
from opennode.oms.model.model.events import IModelModifiedEvent


class IFoo(Interface):
    bar = schema.Int(title=u'bar')


class Foo(object):
    implements(IFoo)

    bar = 1
    __parent__ = object()


def test_apply_and_create_preconditions():
    """There must be no validation errors in objects being updated or created"""
    a = RawDataValidatingFactory({}, Foo)
    assert a.errors
    with assert_raises(AssertionError) as cm:
        a.create()  # should not be able to call `create` with validation errors
    assert cm.exception.args == ("There must be no validation errors", )

    a = RawDataApplier({'bar': 'bad int'}, Foo())
    assert a.errors
    with assert_raises(AssertionError) as cm:
        a.apply()
    assert cm.exception.args == ("There must be no validation errors", )


def test_create_with_missing_required_field():
    a = RawDataValidatingFactory({}, Foo)
    assert repr(a.errors) == "[('bar', RequiredMissing('bar'))]"


def test_apply_with_no_new_value():
    foo = Foo()
    foo.bar = 1
    a = RawDataApplier({}, foo)
    assert not a.errors
    a.apply()
    assert foo.bar == 1


def test_with_invalid_value():
    foo = Foo()

    a = RawDataApplier({'bar': 'not int'}, foo)
    assert repr(a.errors).startswith('[(\'bar\', WrongType')

    a = RawDataApplier({'bar': ''}, foo)
    assert repr(a.errors).startswith('[(\'bar\', RequiredMissing')


def test_create_when_required_field_ok():
    a = RawDataValidatingFactory({'bar': '1'}, Foo)
    assert not a.errors
    foo = a.create()
    assert isinstance(foo, Foo)
    assert foo.bar == 1


def test_apply_with_valid_new_value():
    foo = Foo()
    a = RawDataApplier({'bar': '2'}, obj=foo)
    a.apply()
    assert foo.bar == 2


def test_handler():
    modified = []

    @adapter(IFoo, IModelModifiedEvent)
    def fooModified(foo, event):
        modified.append(event.modified)

    provideHandler(fooModified)

    foo = Foo()
    a = RawDataApplier({'bar': '2'}, foo)
    a.apply()

    assert modified[0] == {'bar': 2}
