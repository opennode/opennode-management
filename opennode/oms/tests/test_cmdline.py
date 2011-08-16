import unittest

import mock
from nose.tools import eq_

from opennode.oms.endpoint.ssh.cmd import cmd_ls

from opennode.oms.endpoint.ssh.cmdline import VirtualConsoleArgumentParser, InstrumentableArgumentParser, ArgumentParsingError, ICmdArgumentsSyntax
from grokcore.component import Subscription, implements, queryOrderedSubscriptions, querySubscriptions, context
from zope.component import provideSubscriptionAdapter

from opennode.oms.endpoint.ssh.completion import ICompleter

class CmdLineParserTestCase(unittest.TestCase):

    def setUp(self):
        self.terminal = mock.Mock()
        self.parser = VirtualConsoleArgumentParser(file=self.terminal)

    def test_help(self):
        self.parser.add_argument('somearg')

        self.parser.print_help()

        assert len(self.terminal.method_calls) == 1
        eq_(self.terminal.method_calls[0][0], 'write')

    def test_exit(self):
        got_exception = False
        try:
            self.parser.parse_args(['--invalid'])
        except ArgumentParsingError as e:
            got_exception = True

        assert got_exception

    def test_partial(self):
        self.parser.add_argument('--foo')
        self.parser.add_argument('--bar')

        args = self.parser.parse_args('--foo'.split(' '), partial=True)
        assert args.foo == None
        assert args.bar == None


class CmdLineTestCase(unittest.TestCase):

    def setUp(self):
        self.protocol = mock.Mock()
        import opennode.oms.endpoint.ssh.cmd
        self.cmd = cmd_ls(self.protocol)

    def test_simple(self):
        arg_parsers = queryOrderedSubscriptions(self.cmd, ICmdArgumentsSyntax)
        eq_(len(arg_parsers), 1)
