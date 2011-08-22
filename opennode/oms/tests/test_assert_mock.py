import unittest
from mock import Mock

from nose.tools import assert_raises

from opennode.oms.tests.util import assert_mock, assert_not_raises
from opennode.oms.tests.util import skip
from opennode.oms.tests.util import no_more_calls
from opennode.oms.tests.util import current_call


class AssertMockTestCase(unittest.TestCase):

    def setUp(self):
        self.mock = Mock()

    def test_basic(self):
        with assert_not_raises():
            with assert_mock(self.mock):
                pass

    def test_no_call(self):
        with assert_raises(AssertionError) as cm:
            with assert_mock(self.mock) as m:
                m.foo()
        assert cm.exception.args == ("Expected a foo() call but instead there was no call", )

    def test_one_call(self):
        self.mock.foo()

        with assert_not_raises():
            with assert_mock(self.mock):
                pass

        with assert_not_raises():
            with assert_mock(self.mock) as m:
                m.foo()

        with assert_raises(AssertionError) as cm:
            with assert_mock(self.mock) as m:
                m.foo()
                m.foo()
        assert cm.exception.args == ("Expected a foo() call but instead there was no call", )

    def test_with_wrong_name(self):
        self.mock.foo()

        with assert_raises(AssertionError) as cm:
            with assert_mock(self.mock) as m:
                m.bar()
        assert cm.exception.args == ("Expected a bar() call but found foo() instead", )

    def test_with_wrong_args(self):
        self.mock.foo('bar')

        with assert_raises(AssertionError) as cm:
            with assert_mock(self.mock) as m:
                m.foo()
        assert cm.exception.args == ("Expected a foo() call but found foo('bar') instead", )


        self.mock.reset_mock()
        self.mock.foo()

        with assert_raises(AssertionError) as cm:
            with assert_mock(self.mock) as m:
                m.foo('bar')
        assert cm.exception.args == ("Expected a foo('bar') call but found foo() instead", )

    def test_with_wrong_kwargs(self):
        self.mock.foo(arg='bar')

        with assert_raises(AssertionError) as cm:
            with assert_mock(self.mock) as m:
                m.foo()
        assert cm.exception.args == ("Expected a foo() call but found foo(arg='bar') instead", )


        self.mock.reset_mock()
        self.mock.foo()

        with assert_raises(AssertionError) as cm:
            with assert_mock(self.mock) as m:
                m.foo(arg='bar')
        assert cm.exception.args == ("Expected a foo(arg='bar') call but found foo() instead", )

    def test_with_wrong_args_and_kwargs(self):
        self.mock.foo('bar', arg='baz')

        with assert_raises(AssertionError) as cm:
            with assert_mock(self.mock) as m:
                m.foo()
        assert cm.exception.args == ("Expected a foo() call but found foo('bar', arg='baz') instead", )

        with assert_raises(AssertionError) as cm:
            with assert_mock(self.mock) as m:
                m.foo('bar')
        assert cm.exception.args == ("Expected a foo('bar') call but found foo('bar', arg='baz') instead", )

        with assert_raises(AssertionError) as cm:
            with assert_mock(self.mock) as m:
                m.foo(arg='baz')
        assert cm.exception.args == ("Expected a foo(arg='baz') call but found foo('bar', arg='baz') instead", )

        with assert_raises(AssertionError) as cm:
            with assert_mock(self.mock) as m:
                m.foo(1, arg=2)
        assert cm.exception.args == ("Expected a foo(1, arg=2) call but found foo('bar', arg='baz') instead", )

    def test_with_correct_args(self):

        self.mock.foo()
        self.mock.bar()
        self.mock.foo(1)
        self.mock.foo(1, 2)
        self.mock.bar(1, 2, 3)
        self.mock.foo(1, 2, a=3, b=4)
        self.mock.foo(1, 2, a=3, b=4)

        with assert_not_raises():
            with assert_mock(self.mock) as m:
                m.foo()
                m.bar()
                m.foo(1)
                m.foo(1, 2)
                m.bar(1, 2, 3)
                m.foo(1, 2, a=3, b=4)
                m.foo(1, 2, a=3, b=4)

    def test_no_more_calls(self):
        with assert_not_raises():
            with assert_mock(self.mock) as m:
                no_more_calls(m)

        self.mock.foo()

        with assert_raises(AssertionError) as cm:
            with assert_mock(self.mock) as m:
                no_more_calls(m)
        assert cm.exception.args == ("There should be no more method calls but there are: foo()", )

    def test_skip(self):
        self.mock.foo()
        self.mock.foo()
        self.mock.foo()

        with assert_not_raises():
            with assert_mock(self.mock) as m:
                skip(m, 3)

        with assert_not_raises():
            with assert_mock(self.mock) as m:
                m.foo()
                skip(m, 2)

        with assert_raises(AssertionError) as cm:
            with assert_mock(self.mock) as m:
                skip(m, 4)
        assert cm.exception.args == ("There should be at least 4 more method calls but there are only 3", )

        with assert_raises(AssertionError) as cm:
            with assert_mock(self.mock) as m:
                m.foo()
                skip(m, 4)
        assert cm.exception.args == ("There should be at least 4 more method calls but there are only 2", )

    def test_current_call(self):
        self.mock.foo('one two three')
        self.mock.foo(foo='bar')

        with assert_not_raises():
            with assert_mock(self.mock) as m:
                assert current_call(m).name == 'foo'
                assert 'two' in current_call(m).args[0]
                skip(m, 1)
                assert current_call(m).kwargs['foo'] == 'bar'

    def test_current_call_as_contextmanager(self):
        self.mock.foo('one two three')
        self.mock.foo(foo='bar')

        with assert_not_raises():
            with assert_mock(self.mock) as m:

                with current_call(m) as c:
                    c.name == 'foo'
                    assert 'two' in c.args[0]

                # No need to `skip(m, 1)` as above.

                with current_call(m) as c:
                    assert c.kwargs['foo'] == 'bar'

                no_more_calls(m)

    def test_current_call_with_single_arg(self):
        self.mock.foo('bar')

        with assert_not_raises():
            with assert_mock(self.mock) as m:
                with current_call(m) as c:
                    c.arg == 'bar'

        self.mock.reset_mock()

        self.mock.foo('bar', 'baz')

        with assert_raises(AssertionError) as cm:
            with assert_mock(self.mock) as m:
                with current_call(m) as c:
                    c.arg
        assert cm.exception.args == ("Call should only have a single argument", )
