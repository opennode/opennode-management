import unittest

import mock
from nose.tools import eq_
from twisted.conch.insults.insults import ServerProtocol

from opennode.oms.endpoint.ssh.terminal import InteractiveTerminal, CTRL_T, CTRL_D, CTRL_L, CTRL_K, CTRL_A, CTRL_Y


class TerminalTestCase(unittest.TestCase):

    def setUp(self):
        self.shell = InteractiveTerminal()
        self.terminal = mock.Mock()
        self.terminal.LEFT_ARROW = ServerProtocol.LEFT_ARROW
        self.terminal.RIGHT_ARROW = ServerProtocol.RIGHT_ARROW
        self.terminal.BACKSPACE = ServerProtocol.BACKSPACE
        self.terminal.ALT = ServerProtocol.ALT

        self.shell.terminal = self.terminal

        self.shell.connectionMade()
        self.terminal.reset_mock()

    def _type(self, text):

        for ch in text:
            self.shell.keystrokeReceived(ch, None)

    def test_EOF(self):
        self._type("test")
        self.terminal.reset_mock()

        self.shell.keystrokeReceived(CTRL_D, None)
        eq_(self.terminal.method_calls, [('write', ('\a',), {})])

        self._type('\n')
        self.terminal.reset_mock()

        self.shell.keystrokeReceived(CTRL_D, None)
        eq_(self.terminal.transport.method_calls, [('loseConnection', (), {})])

    def test_FF(self):
        self.shell.keystrokeReceived(CTRL_L, None)
        eq_(self.terminal.method_calls, [('eraseDisplay', (), {}),
                                         ('cursorHome', (), {}),
                                         ('write', (self.shell.ps[self.shell.pn],), {})])

    def test_delete(self):
        msg = "hello world"

        self._type(msg)
        eq_(''.join(self.shell.lineBuffer), msg)
        eq_(len(self.terminal.method_calls), len(msg))

        self.terminal.reset_mock()

        self.shell.keystrokeReceived(ServerProtocol.BACKSPACE, ServerProtocol.ALT)

        eq_(self.terminal.method_calls, [('cursorBackward', (5,), {}), ('deleteCharacter', (5,), {})])
        eq_(''.join(self.shell.lineBuffer), "hello ")

    def test_transpose(self):
        self._type("ci")
        eq_(''.join(self.shell.lineBuffer), "ci")

        self.shell.keystrokeReceived(CTRL_T, None)
        eq_(''.join(self.shell.lineBuffer), "ic")

        self.shell.keystrokeReceived(ServerProtocol.LEFT_ARROW, None)
        self.shell.keystrokeReceived(ServerProtocol.LEFT_ARROW, None)
        self.shell.keystrokeReceived(CTRL_T, None)
        eq_(''.join(self.shell.lineBuffer), "ci")

        self._type("ao")
        eq_(''.join(self.shell.lineBuffer), "ciao")
        eq_(self.shell.lineBufferIndex, 4)

        self.shell.keystrokeReceived(ServerProtocol.LEFT_ARROW, None)
        self.shell.keystrokeReceived(ServerProtocol.LEFT_ARROW, None)
        self.shell.keystrokeReceived(CTRL_T, None)
        eq_(''.join(self.shell.lineBuffer), "caio")
        eq_(self.shell.lineBufferIndex, 3)

    def test_cut_paste(self):
        self._type("hello world")
        for i in xrange(0, 6):
            self.shell.keystrokeReceived(ServerProtocol.LEFT_ARROW, None)
        self.terminal.reset_mock()

        self.shell.keystrokeReceived(CTRL_K, None)

        eq_(''.join(self.shell.lineBuffer), "hello")
        eq_(self.shell.lineBufferIndex, 5)
        eq_(''.join(self.shell.kill_ring), " world")
        eq_(self.terminal.method_calls, [('eraseToLineEnd', (), {})])

        self.terminal.reset_mock()
        self.shell.keystrokeReceived(CTRL_A, None)
        eq_(self.terminal.method_calls, [('cursorBackward', (5,), {})])

        self.terminal.reset_mock()
        self.shell.keystrokeReceived(CTRL_Y, None)

        eq_(self.terminal.method_calls, [('write', (' world',), {})])
        eq_(''.join(self.shell.lineBuffer), " worldhello")
        eq_(self.shell.lineBufferIndex, 6)
