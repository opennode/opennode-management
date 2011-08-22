import unittest

import mock
from nose.tools import eq_
from zope.interface import implements, Interface

from opennode.oms.endpoint.ssh.protocol import OmsSshProtocol
from opennode.oms.endpoint.ssh.cmd.base import Cmd
from opennode.oms.endpoint.ssh.cmd import registry, commands
from opennode.oms.model.model.compute import Compute
from opennode.oms.model.model.base import Model, Container, SequentialIntegerIdPolicy
from opennode.oms.model.model import creatable_models
from opennode.oms.tests.util import run_in_reactor, assert_mock, no_more_calls, skip
from opennode.oms.zodb import db
from opennode.oms.tests.util import current_call


class CmdCompletionTestCase(unittest.TestCase):

    def setUp(self):
        self.old_id_allocation_policy = Container.id_allocation_policy
        Container.id_allocation_policy = SequentialIntegerIdPolicy()

        self.oms_ssh = OmsSshProtocol()
        self.terminal = mock.Mock()
        self.oms_ssh.terminal = self.terminal

        self.oms_ssh.connectionMade()

        # the standard model doesn't have any command or path which
        # is a prefix of another (len > 1), I don't want to force changes
        # to the model just for testing completion, so we have monkey patch
        # the commands() function and add a command 'hello'.
        self.orig_commands = registry.commands
        registry.commands = lambda: dict(hello=Cmd, **self.orig_commands())

    def tearDown(self):
        Container.id_allocation_policy = self.old_id_allocation_policy
        registry.commands = self.orig_commands

    def _input(self, string):
        for s in string:
            self.oms_ssh.characterReceived(s, False)

    def _tab_after(self, string):
        self._input(string)
        self.terminal.reset_mock()

        self.oms_ssh.handle_TAB()

    def test_command_completion(self):
        self._tab_after('s')
        with assert_mock(self.terminal) as t:
            t.write('et ')
            no_more_calls(t)

    def test_command_completion_spaces(self):
        self._tab_after('    s')
        with assert_mock(self.terminal) as t:
            t.write('et ')
            no_more_calls(t)

    def test_complete_not_found(self):
        self._tab_after('t')
        with assert_mock(self.terminal) as t:
            no_more_calls(t)

    def test_complete_quotes(self):
        self._tab_after('ls "comp')
        with assert_mock(self.terminal) as t:
            t.write('utes/')
            no_more_calls(t)

    def test_complete_prefix(self):
        self._tab_after('h')
        with assert_mock(self.terminal) as t:
            t.write('el')
            no_more_calls(t)

        # hit tab twice
        self.terminal.reset_mock()
        self.oms_ssh.handle_TAB()

        with assert_mock(self.terminal) as t:
            t.write('')
            t.nextLine()
            t.write('help  hello\n')
            t.write(self.oms_ssh.ps[0] + 'hel')
            no_more_calls(t)

    def test_spaces_between_arg(self):
        self._tab_after('ls comp')

        with assert_mock(self.terminal) as t:
            t.write('utes/')
            no_more_calls(t)

    def test_command_arg_spaces_before_command(self):
        self._tab_after(' ls comp')
        with assert_mock(self.terminal) as t:
            t.write('utes/')
            no_more_calls(t)

    def test_mandatory_positional(self):
        self._tab_after('cat ')
        with assert_mock(self.terminal) as t:
            skip(t, 4)
            no_more_calls(t)

    def test_complete_switches(self):
        self._tab_after('quit ')
        with assert_mock(self.terminal) as t:
            no_more_calls(t)

        # hit tab twice
        self.oms_ssh.handle_TAB()
        with assert_mock(self.terminal) as t:
            no_more_calls(t)

        # now try with a dash
        self._tab_after('-')
        with assert_mock(self.terminal) as t:
            t.write('')
            t.nextLine()
            t.write('-h  --help\n')
            t.write(self.oms_ssh.ps[0] + 'quit -')
            no_more_calls(t)
        # disambiguate
        self._tab_after('-')
        with assert_mock(self.terminal) as t:
            t.write('help ')
            no_more_calls(t)

    def test_complete_consumed_switches(self):
        self._tab_after('ls --help')
        with assert_mock(self.terminal) as t:
            t.write(' ')
            no_more_calls(t)

        self._tab_after('-')
        with assert_mock(self.terminal) as t:
            skip(t, 2)
            with current_call(t) as c:
                assert 'help' not in c.args[0]
                assert '-h' not in c.args[0]

    @run_in_reactor
    def test_complete_context_dependent_no_context(self):
        """Test whether context dependent arguments are correctly built when the
        context argument (i.e. the `set` cmd `path` argument) is not yet present.

        """
        self._tab_after('set /comp')
        eq_(self.terminal.method_calls, [('write', ('utes/',), {})])

    @run_in_reactor
    def test_complete_keyword_switches(self):
        computes = db.get_root()['oms_root']['computes']
        computes.add(Compute('linux', 'tux-for-test', 2000, 2000, 'active'))

        self._tab_after('set /computes/1 arch')
        eq_(self.terminal.method_calls, [('write', ('itecture=',), {})])

        self._tab_after('li')
        eq_(self.terminal.method_calls, [('write', ('nux ',), {})])

    @run_in_reactor
    def test_complete_keyword_switches_mk(self):
        self.oms_ssh.lineReceived('cd computes')

        self._tab_after('mk compute arch')
        eq_(self.terminal.method_calls, [('write', ('itecture=',), {})])

        self._tab_after('li')
        eq_(self.terminal.method_calls, [('write', ('nux ',), {})])

    @run_in_reactor
    def test_complete_consumed_keyword_switches_mk(self):
        """Test consuming of already completed switches when there are mandatory arguments."""
        self.oms_ssh.lineReceived('cd computes')

        self._tab_after('mk compute arch')
        eq_(self.terminal.method_calls, [('write', ('itecture=',), {})])

        self._tab_after('li')
        eq_(self.terminal.method_calls, [('write', ('nux ',), {})])

        self._tab_after('arch')
        eq_(self.terminal.method_calls, [])

    @run_in_reactor
    def test_complete_mk_legal_types(self):
        """Test that only legal types are shown."""
        self.oms_ssh.lineReceived('cd computes')

        self._tab_after('mk net')
        eq_(self.terminal.method_calls, [])

        self.oms_ssh.handle_RETURN()
        self.terminal.reset_mock()

        self._tab_after('mk comp')
        eq_(self.terminal.method_calls, [('write', ('ute ',), {})])

        self._tab_after('arch')
        eq_(self.terminal.method_calls, [('write', ('itecture=',), {})])

    @run_in_reactor
    def test_complete_mk_legal_types_interface(self):
        class ITest(Interface):
            pass

        class Test(Model):
            implements(ITest)

            def __init__(self):
                pass

        class TestInterfaceContainer(Container):
            __contains__ = ITest

        class TestClassContainer(Container):
            __contains__ = Test

        creatable_models['some-test'] = Test

        orig_current_object = commands.CreateObjCmd.current_obj

        try:
            commands.CreateObjCmd.current_obj = TestInterfaceContainer()
            self._tab_after('mk ')
            eq_(self.terminal.method_calls, [('write', ('some-test ',), {})])

            self.oms_ssh.handle_RETURN()
            self.terminal.reset_mock()

            commands.CreateObjCmd.current_obj = TestClassContainer()

            self._tab_after('mk ')
            eq_(self.terminal.method_calls, [('write', ('some-test ',), {})])
        finally:
            commands.CreateObjCmd.current_obj = orig_current_object
            del creatable_models['some-test']

    @run_in_reactor
    def test_complete_positional_choice(self):
        self.oms_ssh.lineReceived('cd computes')

        self._tab_after('mk comp')
        eq_(self.terminal.method_calls, [('write', ('ute ',), {})])

        self._tab_after('comp')
        eq_(self.terminal.method_calls, [])
