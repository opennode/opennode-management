import unittest

import mock

from opennode.oms.endpoint.ssh.protocol import OmsSshProtocol
from opennode.oms.model.model.compute import Compute
from opennode.oms.tests.util import run_in_reactor
from opennode.oms.zodb import db


class SshTestCase(unittest.TestCase):

    def setUp(self):
        self.oms_ssh = OmsSshProtocol()
        self.terminal = mock.Mock()
        self.oms_ssh.terminal = self.terminal

    def _cmd(self, cmd):
        self.oms_ssh.lineReceived(cmd)

    def test_quit(self):
        self._cmd('quit')
        assert self.terminal.method_calls == [('loseConnection', )]

    def test_non_existent_cmd(self):
        self._cmd('non-existent-command')
        assert self.terminal.method_calls[0] == ('write', ('No such command: non-existent-command',))

    @run_in_reactor
    def test_pwd(self):
        self._cmd('pwd')
        assert self.terminal.method_calls[0] == ('write', ('/\n',))

    @run_in_reactor
    def test_cd(self):
        for folder in ['computes', 'templates']:
            for cmd in ['%s', '/%s', '//%s', '/./%s', '%s/.', '/%s/.']:
                self._cmd('cd %s' % (cmd % folder))
                assert self.oms_ssh._cwd() == '/%s' % folder

                self._cmd('cd ..')

    @run_in_reactor
    def test_cd_to_root(self):
        for cmd in ['cd', 'cd /', 'cd //', 'cd ../..', 'cd /..']:
            self._cmd('cd computes')
            assert self.oms_ssh._cwd() == '/computes'
            self._cmd(cmd)
            assert self.oms_ssh._cwd() == '/'
            self.terminal.reset_mock()

    @run_in_reactor
    def test_ls(self):
        self._cmd('ls')
        assert self.terminal.method_calls[0] == ('write', ('templates  computes\n',))

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

        self.terminal.reset_mock()

        computes = db.get_root()['oms_root']['computes']
        computes.add(Compute('linux', 'tux-for-test', 2000, 2000, 'active'))

        self._cmd('cat computes/1')

        assert self.terminal.method_calls[:-1] == [
            ('write', ('Architecture:   \tlinux\n',)),
            ('write', ('CPU Speed in MHz:\t2000\n',)),
            ('write', ('Host name:      \ttux-for-test\n',)),
            ('write', ('RAM size in MB: \t2000\n',)),
            ('write', ('State:          \tactive\n',)),
        ]

    @run_in_reactor
    def test_modify_compute(self):
        computes = db.get_root()['oms_root']['computes']
        computes.add(Compute('linux', 'tux-for-test', 2000, 2000, 'active'))

        self._cmd('set computes/1 hostname=TUX-FOR-TEST')
        self.terminal.reset_mock()

        self._cmd('cat computes/1')
        assert self.terminal.method_calls[:-1] == [
            ('write', ('Architecture:   \tlinux\n',)),
            ('write', ('CPU Speed in MHz:\t2000\n',)),
            ('write', ('Host name:      \tTUX-FOR-TEST\n',)),
            ('write', ('RAM size in MB: \t2000\n',)),
            ('write', ('State:          \tactive\n',)),
        ]
