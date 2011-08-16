import re

from twisted.conch import recvline
from twisted.internet import defer
from twisted.python import log
from columnize import columnize
import os

from opennode.oms.endpoint.ssh import cmd, completion, cmdline
from opennode.oms.endpoint.ssh.tokenizer import CommandLineTokenizer, CommandLineSyntaxError
from opennode.oms.zodb import db


CTRL_A = '\x01'
CTRL_E = '\x05'
CTRL_D = '\x04'
CTRL_K = '\x0b'
CTRL_Y = '\x19'
CTRL_BACKSLASH = '\x1c'
CTRL_L = '\x0c'


class InteractiveTerminal(recvline.HistoricRecvLine):
    """Advanced interactive terminal. Handles history, line editing,
    killing/yanking, line movement.

    Prompt handling is delegated to subclasses.
    """

    def connectionMade(self):
        super(InteractiveTerminal, self).connectionMade()

        self.history_save_enabled = True
        self.restore_history()

        self.kill_ring = None
        self.keyHandlers[CTRL_A] = self.handle_HOME
        self.keyHandlers[CTRL_E] = self.handle_END
        self.keyHandlers[CTRL_D] = self.handle_EOF
        self.keyHandlers[CTRL_L] = self.handle_FF
        self.keyHandlers[CTRL_K] = self.handle_KILL_LINE
        self.keyHandlers[CTRL_Y] = self.handle_YANK
        self.keyHandlers[CTRL_BACKSLASH] = self.handle_QUIT

    def restore_history(self):
        try:
            if os.path.exists(self.hist_file_name):
                self.historyLines = [line.strip() for line in open(self.hist_file_name, 'r').readlines()]
                self.historyPosition = len(self.historyLines)
        except Exception as e:
            log.msg("cannot restore history: %s" % e)

    def save_history(self):
        if not self.history_save_enabled:
            return

        try:
            open(self.hist_file_name, 'w').writelines([line + '\n' for line in self.historyLines])
        except Exception as e:
            log.msg("cannot save history: %s" % e)

    @property
    def hist_file_name(self):
        raise Exception("subclass must override")

    def handle_EOF(self):
        """Exit the shell on CTRL-D"""
        if self.lineBuffer:
            self.terminal.write('\a')
        else:
            self.handle_QUIT()

    def handle_FF(self):
        """Handle a 'form feed' byte - generally used to request a screen
        refresh/redraw.
        """
        self.terminal.eraseDisplay()
        self.terminal.cursorHome()
        self.drawInputLine()

    def handle_KILL_LINE(self):
        """Deletes the rest of the line (from the cursor right), and keeps the content
        in the kill ring for future pastes
        """
        self.terminal.eraseToLineEnd()
        self.kill_ring = self.lineBuffer[self.lineBufferIndex:]
        self.lineBuffer = self.lineBuffer[0:self.lineBufferIndex]

    def handle_YANK(self):
        """Paste the content of the kill ring"""
        if self.kill_ring:
            self.terminal.write("".join(self.kill_ring))
            self.insert_buffer(self.kill_ring)

    def handle_QUIT(self):
        """Just copied from conch Manhole, no idea why it would be useful to differentiate it from CTRL-D,
        but I guess it's here for a reason"""
        self.close_connection()

    def close_connection(self):
        """Closes the connection and saves history."""

        self.save_history()
        self.terminal.loseConnection()
