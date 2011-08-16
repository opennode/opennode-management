import unittest

import mock
from nose.tools import eq_

from opennode.oms.endpoint.ssh.protocol import OmsSshProtocol
from opennode.oms.endpoint.ssh import cmd


class CmdCompletionTestCase(unittest.TestCase):

    def setUp(self):
        self.oms_ssh = OmsSshProtocol()
        self.terminal = mock.Mock()
        self.oms_ssh.terminal = self.terminal

        self.oms_ssh.connectionMade()

        # the standard model doesn't have any command or path which
        # is a prefix of another (len > 1), I don't want to force changes
        # to the model just for testing completion, so we have monkey patch
        # the commands() function and add a command 'hello'.
        self.orig_commands = cmd.commands
        cmd.commands = lambda: dict(hello=cmd.Cmd, **self.orig_commands())

    def tearDown(self):
        cmd.commands = self.orig_commands

    def _input(self, string):
        for s in string:
            self.oms_ssh.characterReceived(s, False)

    def _tab_after(self, string):
        self._input(string)
        self.terminal.reset_mock()

        self.oms_ssh.handle_TAB()

    def test_command_completion(self):
        self._tab_after('s')
        eq_(self.terminal.method_calls, [('write', ('et ',), {})])

    def test_command_completion_spaces(self):
        self._tab_after('    s')
        eq_(self.terminal.method_calls, [('write', ('et ',), {})])

    def test_complete_not_found(self):
        self._tab_after('t')
        eq_(len(self.terminal.method_calls), 0)

    def test_complete_quotes(self):
        self._tab_after('ls "comp')
        eq_(self.terminal.method_calls, [('write', ('utes" ',), {})])

    def test_complete_prefix(self):
        self._tab_after('h')
        eq_(self.terminal.method_calls, [('write', ('el',), {})])

        # hit tab twice
        self.terminal.reset_mock()
        self.oms_ssh.handle_TAB()

        eq_(self.terminal.method_calls, [('write', ('',), {}), ('nextLine', (), {}), ('write', ('help  hello\n',), {}), ('write', (self.oms_ssh.ps[0] + 'hel',), {})])

    def test_spaces_between_arg(self):
        self._tab_after('ls comp')
        eq_(self.terminal.method_calls, [('write', ('utes ',), {})])

    def test_command_arg_spaces_before_command(self):
        self._tab_after(' ls comp')
        eq_(self.terminal.method_calls, [('write', ('utes ',), {})])

    def test_mandatory_positional(self):
        self._tab_after('cat ')
        eq_(len(self.terminal.method_calls), 4)

    def test_complete_switches(self):
        self._tab_after('quit ')
        eq_(len(self.terminal.method_calls), 0)

        # hit tab twice
        self.oms_ssh.handle_TAB()
        eq_(len(self.terminal.method_calls), 0)

        # now try with a dash
        self._tab_after('-')
        eq_(self.terminal.method_calls, [('write', ('',), {}), ('nextLine', (), {}), ('write', ('-h  --help\n',), {}), ('write', (self.oms_ssh.ps[0] + 'quit -',), {})])
        # disambiguate
        self._tab_after('-')
        eq_(self.terminal.method_calls, [('write', ('help ',), {})])

    def test_complete_consumed_switches(self):
        self._tab_after('ls --help')
        eq_(self.terminal.method_calls, [('write', (' ',), {})])

        self._tab_after('-')
        assert 'help' not in self.terminal.method_calls[2][1][0]
        assert '-h' not in self.terminal.method_calls[2][1][0]
