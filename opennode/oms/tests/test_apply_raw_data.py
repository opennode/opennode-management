from nose.tools import assert_raises
from zope import schema
from zope.component import adapter, provideHandler
from zope.interface import Interface, implements

from opennode.oms.model.form import ApplyRawData, IModelModifiedEvent


class IFoo(Interface):
    bar = schema.Int(title=u'bar')


class Foo(object):
    implements(IFoo)

    bar = 1


def test_apply_and_create_preconditions():
    """Tests that `create` and `apply` require that there are no
    validation errors and that `create` requires a model class, and
    `apply` an existing object to be passed in.

    """
    a = ApplyRawData({}, model=Foo)
    with assert_raises(AssertionError) as cm:
        a.apply()
    assert cm.exception.args == ("obj needs to be provided to apply changes to an existing object", )

    assert a.errors
    with assert_raises(AssertionError) as cm:
        a.create()  # should not be able to call `create` with validation errors
    assert cm.exception.args == ("There should be no validation errors", )


    a = ApplyRawData({'bar': 'bad int'}, obj=Foo())
    with assert_raises(AssertionError) as cm:
        a.create()
    assert cm.exception.args == ("model needs to be provided to create new objects", )

    assert a.errors
    with assert_raises(AssertionError) as cm:
        a.apply()
    assert cm.exception.args == ("There should be no validation errors", )


def test_create_with_missing_required_field():
    a = ApplyRawData({}, model=Foo)
    assert repr(a.errors) == "[('bar', RequiredMissing('bar'))]"


def test_apply_with_no_new_value():
    foo = Foo(); foo.bar = 1
    a = ApplyRawData({}, obj=foo)
    assert not a.errors
    a.apply()
    assert foo.bar == 1


def test_with_invalid_value():
    foo = Foo()

    a = ApplyRawData({'bar': 'not int'}, obj=foo)
    assert repr(a.errors).startswith('[(\'bar\', WrongType')

    a = ApplyRawData({'bar': ''}, obj=foo)
    assert repr(a.errors).startswith('[(\'bar\', RequiredMissing')


def test_create_when_required_field_ok():
    a = ApplyRawData({'bar': '1'}, model=Foo)
    assert not a.errors
    foo = a.create()
    assert isinstance(foo, Foo)
    assert foo.bar == 1


def test_apply_with_valid_new_value():
    foo = Foo()
    a = ApplyRawData({'bar': '2'}, obj=foo)
    a.apply()
    assert foo.bar == 2

def test_handler():
    modified = []

    @adapter(IFoo, IModelModifiedEvent)
    def fooModified(foo, event):
        modified.append(event.modified)

    provideHandler(fooModified)

    foo = Foo()
    a = ApplyRawData({'bar': '2'}, obj=foo)
    a.apply()

    assert modified[0] == {'bar': 2}
