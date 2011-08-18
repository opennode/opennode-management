import unittest

import mock
from nose.tools import eq_

from opennode.oms.endpoint.ssh.terminal import InteractiveTerminal, CTRL_T
from twisted.conch.insults.insults import ServerProtocol

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
