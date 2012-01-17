import unittest

import mock
import transaction
from zope.interface import implements, Interface

from opennode.oms.endpoint.ssh.cmd import registry, commands
from opennode.oms.endpoint.ssh.cmd.base import Cmd
from opennode.oms.endpoint.ssh.protocol import OmsShellProtocol
from opennode.oms.model.model import creatable_models
from opennode.oms.model.model.base import Model, Container
from opennode.oms.tests.test_compute import Compute
from opennode.oms.tests.util import run_in_reactor, assert_mock, no_more_calls, skip, current_call
from opennode.oms.zodb import db


class CmdCompletionTestCase(unittest.TestCase):

    def setUp(self):
        self.oms_ssh = OmsShellProtocol()
        self.oms_ssh.logged_in(None)
        self.terminal = mock.Mock()
        self.oms_ssh.terminal = self.terminal

        self.oms_ssh.connectionMade()

        # the standard model doesn't have any command or path which
        # is a prefix of another (len > 1), I don't want to force changes
        # to the model just for testing completion, so we have monkey patch
        # the commands() function and add a command 'hello'.
        self.orig_commands = registry.commands

        class HelloCmd(Cmd):
            name = 'hello'
        registry.commands = lambda: dict(hello=HelloCmd, **self.orig_commands())

    def tearDown(self):
        registry.commands = self.orig_commands

    def make_compute(self, hostname=u'tux-for-test', state=u'active', arch=u'linux', memory=2000):
        return Compute(hostname, state, arch, memory)

    def _input(self, string):
        for s in string:
            self.oms_ssh.characterReceived(s, False)

    def _tab_after(self, string):
        self._input(string)
        self.terminal.reset_mock()

        self.oms_ssh.handle_TAB()

    def test_command_completion(self):
        self._tab_after('q')
        with assert_mock(self.terminal) as t:
            t.write('uit ')
            no_more_calls(t)

    def test_command_completion_spaces(self):
        self._tab_after('    q')
        with assert_mock(self.terminal) as t:
            t.write('uit ')
            no_more_calls(t)

    def test_complete_not_found(self):
        self._tab_after('asdasd')
        with assert_mock(self.terminal) as t:
            no_more_calls(t)

    def test_complete_quotes(self):
        self._tab_after('ls "comp')
        with assert_mock(self.terminal) as t:
            t.write('utes/')
            no_more_calls(t)

    def test_complete_prefix(self):
        self._tab_after('he')
        with assert_mock(self.terminal) as t:
            t.write('l')
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
                assert 'help' not in c.arg
                assert '-h' not in c.arg

    @run_in_reactor
    def test_complete_context_dependent_no_context(self):
        """Test whether context dependent arguments are correctly built when the
        context argument (i.e. the `set` cmd `path` argument) is not yet present.

        """
        self._tab_after('set /comp')
        with assert_mock(self.terminal) as t:
            t.write('utes/')
            no_more_calls(t)

    @run_in_reactor
    def test_complete_keyword_switches(self):
        computes = db.get_root()['oms_root']['computes']
        cid = computes.add(self.make_compute())
        transaction.commit()

        self._tab_after('set /computes/%s st' % cid)
        with assert_mock(self.terminal) as t:
            t.write('ate=')
            no_more_calls(t)

        self._tab_after('ina')
        with assert_mock(self.terminal) as t:
            t.write('ctive ')
            no_more_calls(t)

    @run_in_reactor
    def test_complete_keyword_switches_mk(self):
        self.oms_ssh.lineReceived('cd computes')

        self._tab_after('mk compute st')
        with assert_mock(self.terminal) as t:
            t.write('ate=')
            no_more_calls(t)

        self._tab_after('ina')
        with assert_mock(self.terminal) as t:
            t.write('ctive ')
            no_more_calls(t)

    @run_in_reactor
    def test_complete_consumed_keyword_switches_mk(self):
        """Test consuming of already completed switches when there are mandatory arguments."""
        self.oms_ssh.lineReceived('cd computes')

        self._tab_after('mk compute st')
        with assert_mock(self.terminal) as t:
            t.write('ate=')
            no_more_calls(t)

        self._tab_after('ina')
        with assert_mock(self.terminal) as t:
            t.write('ctive ')
            no_more_calls(t)

        self._tab_after('st')
        assert not self.terminal.method_calls

    @run_in_reactor
    def test_complete_mk_legal_types(self):
        """Test that only legal types are shown."""
        self.oms_ssh.lineReceived('cd computes')

        self._tab_after('mk net')
        assert not self.terminal.method_calls

        self.oms_ssh.handle_RETURN()
        self.terminal.reset_mock()

        self._tab_after('mk comp')
        #~ eq_(self.terminal.method_calls, [('write', ('ute ',), {})])
        with assert_mock(self.terminal) as t:
            t.write('ute ')
            no_more_calls(t)

        self._tab_after('arch')
        with assert_mock(self.terminal) as t:
            t.write('itecture=')
            no_more_calls(t)

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
            with assert_mock(self.terminal) as t:
                t.write('some-test ')
                no_more_calls(t)

            self.oms_ssh.handle_RETURN()
            self.terminal.reset_mock()

            commands.CreateObjCmd.current_obj = TestClassContainer()

            self._tab_after('mk ')
            with assert_mock(self.terminal) as t:
                t.write('some-test ')
                no_more_calls(t)
        finally:
            commands.CreateObjCmd.current_obj = orig_current_object
            del creatable_models['some-test']

    @run_in_reactor
    def test_complete_positional_choice(self):
        self.oms_ssh.lineReceived('cd computes')

        self._tab_after('mk comp')
        with assert_mock(self.terminal) as t:
            t.write('ute ')
            no_more_calls(t)

        self._tab_after('comp')
        assert not self.terminal.method_calls

    @run_in_reactor
    def test_complete_container_symlink(self):
        computes = db.get_root()['oms_root']['computes']
        cid = computes.add(self.make_compute())
        transaction.commit()

        self._tab_after('cd /computes/%s' % cid)
        with assert_mock(self.terminal) as t:
            t.write('/')
