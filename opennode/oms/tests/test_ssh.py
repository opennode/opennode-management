import unittest

import mock
from nose.tools import eq_
from zope.interface import implements, Interface
from martian.testing import FakeModule
from grokcore.component.testing import grok

from opennode.oms.endpoint.ssh.protocol import OmsSshProtocol, CommandLineSyntaxError
from opennode.oms.endpoint.ssh.cmd.base import Cmd
from opennode.oms.endpoint.ssh.cmd.commands import CreateObjCmd
from opennode.oms.endpoint.ssh.cmd.directives import command
from opennode.oms.endpoint.ssh.cmd.registry import commands
from opennode.oms.model.model.compute import Compute
from opennode.oms.model.model.base import Model, Container
from opennode.oms.model.model import creatable_models
from opennode.oms.tests.util import run_in_reactor, clean_db
from opennode.oms.zodb import db
from opennode.oms.tests.util import assert_mock, no_more_calls, skip


class SshTestCase(unittest.TestCase):

    @run_in_reactor
    @clean_db
    def setUp(self):
        self.oms_ssh = OmsSshProtocol()
        self.oms_ssh.history_save_enabled = False

        self.terminal = mock.Mock()
        self.oms_ssh.terminal = self.terminal

        self.oms_ssh.enable_colors = False

    def _cmd(self, cmd):
        self.oms_ssh.lineReceived(cmd)

    def test_quit(self):
        self._cmd('quit')
        with assert_mock(self.terminal) as t:
            t.loseConnection()
            t.write('user@oms:/# ')

    def test_non_existent_cmd(self):
        self._cmd('non-existent-command')
        with assert_mock(self.terminal) as t:
            t.write('No such command: non-existent-command\n')

    @run_in_reactor
    def test_pwd(self):
        self._cmd('pwd')
        with assert_mock(self.terminal) as t:
            t.write('/\n')

    @run_in_reactor
    def test_help(self):
        self._cmd('help')
        out = self.terminal.method_calls[0][1][0]
        for c in commands().keys():
            assert c in out

    @run_in_reactor
    def test_cd(self):
        for folder in ['computes', 'templates']:
            for cmd in ['%s', '/%s', '//%s', '/./%s', '%s/.', '/%s/.']:
                self._cmd('cd %s' % (cmd % folder))
                assert self.oms_ssh._cwd() == '/%s' % folder

                self._cmd('cd ..')

    @run_in_reactor
    def test_cd_errors(self):
        computes = db.get_root()['oms_root']['computes']
        computes.add(Compute('linux', 'tux-for-test', 2000, 2000, 'active'))

        self._cmd('cd /computes/1')
        with assert_mock(self.terminal) as t:
            t.write('Cannot cd to a non-container\n')

        self.terminal.reset_mock()

        self._cmd('cd /nonexisting')
        with assert_mock(self.terminal) as t:
            t.write('No such object: /nonexisting\n')

    @run_in_reactor
    def test_cd_to_root(self):
        for cmd in ['cd', 'cd /', 'cd //', 'cd ../..', 'cd /..', 'cd']:
            self._cmd('cd computes')
            assert self.oms_ssh._cwd() == '/computes'
            self._cmd(cmd)
            assert self.oms_ssh._cwd() == '/'
            self.terminal.reset_mock()

    @run_in_reactor
    def test_ls(self):
        self._cmd('ls')
        with assert_mock(self.terminal) as t:
            t.write('templates/  computes/\n')

        self._cmd('ls /')
        with assert_mock(self.terminal) as t:
            t.write('templates/  computes/\n')

        computes = db.get_root()['oms_root']['computes']
        computes.add(Compute('linux', 'tux-for-test', 2000, 2000, 'active'))

        self.terminal.reset_mock()
        self._cmd('ls /computes/1')
        with assert_mock(self.terminal) as t:
            t.write('/computes/1\n')

        self.terminal.reset_mock()
        self._cmd('ls /computes/x')
        with assert_mock(self.terminal) as t:
            t.write('No such object: /computes/x\n')

    @run_in_reactor
    def test_ls_l(self):
        self.terminal.reset_mock()
        self._cmd('ls /computes -l')
        #~ assert self.terminal.method_calls[:-1] == []
        with assert_mock(self.terminal) as t:
            skip(t, 1)
            no_more_calls(t)

        computes = db.get_root()['oms_root']['computes']
        computes.add(Compute('linux', 'tux-for-test', 2000, 2000, 'active'))

        self.terminal.reset_mock()
        self._cmd('ls /computes -l')
        with assert_mock(self.terminal) as t:
            t.write('1\tc1:compute1:tux-for-test\n')
            skip(t, 1)
            no_more_calls(t)

        self.terminal.reset_mock()
        self._cmd('ls /computes/1 -l')
        with assert_mock(self.terminal) as t:
            t.write('1\tc1:compute1:tux-for-test\n')
            skip(t, 1)
            no_more_calls(t)

    @run_in_reactor
    def test_cat_folders(self):
        for folder in ['computes', 'templates']:
            self._cmd('cat %s' % folder)
            assert self.terminal.method_calls[0] == ('write', ('Unable to create a printable representation.\n', ))
            self.terminal.reset_mock()

    @run_in_reactor
    def test_cat_compute(self):
        self._cmd('cat computes/1')
        assert self.terminal.method_calls[0] == ('write', ("No such object: computes/1\n", ))
        with assert_mock(self.terminal) as t:
            t.write("No such object: computes/1\n")

        self.terminal.reset_mock()

        computes = db.get_root()['oms_root']['computes']
        computes.add(Compute('linux', 'tux-for-test', 2000, 2000, 'active'))

        self._cmd('cat computes/1')

        with assert_mock(self.terminal) as t:
            t.write('Architecture:   \tlinux\n')
            t.write('CPU Speed in MHz:\t2000\n')
            t.write('Host name:      \ttux-for-test\n')
            t.write('RAM size in MB: \t2000\n')
            t.write('State:          \tactive\n')

    @run_in_reactor
    def test_rm_compute(self):
        self._cmd('cat computes/1')
        assert self.terminal.method_calls[0] == ('write', ("No such object: computes/1\n", ))

        self.terminal.reset_mock()

        computes = db.get_root()['oms_root']['computes']
        computes.add(Compute('linux', 'tux-for-test', 2000, 2000, 'active'))

        self._cmd('cat computes/1')

        with assert_mock(self.terminal) as t:
            t.write('Architecture:   \tlinux\n')
            t.write('CPU Speed in MHz:\t2000\n')
            t.write('Host name:      \ttux-for-test\n')
            t.write('RAM size in MB: \t2000\n')
            t.write('State:          \tactive\n')

        self._cmd('rm computes/1')

        self.terminal.reset_mock()

        self._cmd('cat computes/1')
        with assert_mock(self.terminal) as t:
            t.write("No such object: computes/1\n")

        self.terminal.reset_mock()

        self._cmd('rm computes/1')
        with assert_mock(self.terminal) as t:
            t.write("No such object: computes/1\n")

    @run_in_reactor
    def test_modify_compute(self):
        computes = db.get_root()['oms_root']['computes']
        computes.add(Compute('linux', 'tux-for-test', 2000, 2000, 'active'))

        self._cmd('set computes/1 hostname=TUX-FOR-TEST')
        self.terminal.reset_mock()

        self._cmd('cat computes/1')
        with assert_mock(self.terminal) as t:
            t.write('Architecture:   \tlinux\n')
            t.write('CPU Speed in MHz:\t2000\n')
            t.write('Host name:      \tTUX-FOR-TEST\n')
            t.write('RAM size in MB: \t2000\n')
            t.write('State:          \tactive\n')

        self.terminal.reset_mock()
        self._cmd('set computes/123')
        with assert_mock(self.terminal) as t:
            t.write("No such object: computes/123\n")

        self.terminal.reset_mock()
        self._cmd('set computes')
        with assert_mock(self.terminal) as t:
            t.write("No schema found for object: computes\n")

    @run_in_reactor
    def test_modify_compute_verbose(self):
        computes = db.get_root()['oms_root']['computes']
        computes.add(Compute('linux', 'tux-for-test', 2000, 2000, 'active'))

        self._cmd('set computes/1 hostname=TUX-FOR-TEST -v')
        with assert_mock(self.terminal) as t:
            t.write("Setting hostname=TUX-FOR-TEST\n")

        self.terminal.reset_mock()

        self._cmd('cat computes/1')
        with assert_mock(self.terminal) as t:
            t.write('Architecture:   \tlinux\n')
            t.write('CPU Speed in MHz:\t2000\n')
            t.write('Host name:      \tTUX-FOR-TEST\n')
            t.write('RAM size in MB: \t2000\n')
            t.write('State:          \tactive\n')

    @run_in_reactor
    def test_modify_compute_errors(self):
        computes = db.get_root()['oms_root']['computes']
        computes.add(Compute('linux', 'tux-for-test', 2000, 2000, 'active'))

        self._cmd('set computes/1 hostname=x')
        with assert_mock(self.terminal) as t:
            t.write("hostname: Value is too short\n")

    @run_in_reactor
    def test_create_compute(self):
        self._cmd("cd /computes")
        self._cmd("mk compute architecture=linux hostname=TUX-FOR-TEST memory=2000 state=active speed=2000")

        self.terminal.reset_mock()
        self._cmd('cat 1')

        with assert_mock(self.terminal) as t:
            t.write('Architecture:   \tlinux\n')
            t.write('CPU Speed in MHz:\t2000\n')
            t.write('Host name:      \tTUX-FOR-TEST\n')
            t.write('RAM size in MB: \t2000\n')
            t.write('State:          \tactive\n')

    @run_in_reactor
    def test_create_compute_mandatory_args(self):
        self._cmd("cd /computes")

        self.terminal.reset_mock()
        self._cmd("mk compute architecture=linux hostname=TUX-FOR-TEST memory=2000 state=active")

        with assert_mock(self.terminal) as t:
            t.write("argument =speed is required")

    @run_in_reactor
    def test_mk_keyword_declaration(self):
        class ITest(Interface):
            pass

        class Test(Model):
            implements(ITest)

            # The optional arg is important for this test.
            #
            # CreateObjCmd will try to get the value of keyword switches for each
            # parameter of the model constructor, including default ones.
            # However if this optional is not defined in the schema,
            # the argument parser will not contain any argument definition for
            # the 'keywords' option, so the 'keywords' arg object attribute
            # will not be define unless explicitly declared with `arg_declare`.
            def __init__(self, some_optional=None):
                pass

        class TestContainer(Container):
            __contains__ = Test

            added = False

            def add(self, item):
                self.added = True

        creatable_models['some-test'] = Test
        orig_current_object = CreateObjCmd.current_obj

        try:
            CreateObjCmd.current_obj = TestContainer()
            self._cmd('mk some-test')
            assert CreateObjCmd.current_obj.added
        finally:
            CreateObjCmd.current_obj = orig_current_object
            del creatable_models['some-test']

    @run_in_reactor
    def test_context_dependent_help(self):
        computes = db.get_root()['oms_root']['computes']
        computes.add(Compute('linux', 'tux-for-test', 2000, 2000, 'active'))

        self.terminal.reset_mock()
        self._cmd('set computes/1 -h')

        assert 'hostname = ' in self.terminal.method_calls[0][1][0]

    @run_in_reactor
    def test_parsing_error_message(self):
        self._cmd('mk unknown')
        eq_(len(self.terminal.method_calls), 3)

    @run_in_reactor
    def test_last_error(self):
        class meta(FakeModule):
            class FailingCommand(Cmd):
                command('fail')

                def execute(self, args):
                    raise Exception('some mock error')

        grok('martiantest.fake.meta')

        self._cmd('fail')
        self.terminal.reset_mock()
        self._cmd('last_error')
        assert 'some mock error' in self.terminal.method_calls[0][1][0]

    @run_in_reactor
    def test_suggestion(self):
        self._cmd('make')
        with assert_mock(self.terminal) as t:
            skip(t, 1)
            t.write("Do you mean 'mk'?\n")


    def test_tokenizer(self):
        arglist = r'set /computes/some\ file\ \ with\ spaces -v --help key=value other_key="quoted value" "lastkey"="escaped \" quotes"'

        eq_(self.oms_ssh.tokenizer.tokenize(arglist),
                ['set', '/computes/some file  with spaces', '-v', '--help', '=key', 'value', '=other_key', 'quoted value', '=lastkey', 'escaped " quotes'])

        got_exception = False
        try:
            self.oms_ssh.tokenizer.tokenize('ls " -l')
        except CommandLineSyntaxError:
            got_exception = True

        assert got_exception

        # TODO: handle "glued" quoted args
        # arglist = r'set /computes/some\ file\ \ with\ spaces -v --help key=value other_key="quoted value" "lastkey"="escaped \" quotes" cornercase="glued""quoted"'
