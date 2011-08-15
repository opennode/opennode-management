import re

from twisted.conch import recvline
from twisted.internet import defer
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

class OmsSshProtocol(recvline.HistoricRecvLine):
    """Simple echo protocol.

    Accepts lines of input and writes them back to its connection.  If
    a line consisting solely of "quit" is received, the connection
    is dropped.

    """

    def __init__(self):
        super(OmsSshProtocol, self).__init__()
        self.path = ['']

        @defer.inlineCallbacks
        def _get_obj_path():
            # Here, we simply hope that self.obj_path won't actually be
            # used until it's initialised.  A more fool-proof solution
            # would be to block everything in the protocol while the ZODB
            # query is processing, but that would require a more complex
            # workaround.  This will not be a problem during testing as
            # DB access is blocking when testing.
            self.obj_path = yield db.transact(lambda: [db.ref(db.get_root()['oms_root'])])()

        _get_obj_path()

        self.tokenizer = CommandLineTokenizer()

    def connectionMade(self):
        super(OmsSshProtocol, self).connectionMade()

        self.kill_ring = None
        self.keyHandlers[CTRL_A] = self.handle_HOME
        self.keyHandlers[CTRL_E] = self.handle_END
        self.keyHandlers[CTRL_D] = self.handle_EOF
        self.keyHandlers[CTRL_L] = self.handle_FF
        self.keyHandlers[CTRL_K] = self.handle_KILL_LINE
        self.keyHandlers[CTRL_Y] = self.handle_YANK
        self.keyHandlers[CTRL_BACKSLASH] = self.handle_QUIT

    def lineReceived(self, line):
        line = line.strip()

        cmd_name, cmd_args = line.partition(' ')[::2]
        cmd_handler = cmd.commands().get(cmd_name, None)
        if cmd_handler:
            cmd_args = cmd_args.strip()
            if cmd_args:
                cmd_args = self.tokenizer.tokenize(cmd_args)
            else:
                cmd_args = []
            deferred = defer.maybeDeferred(cmd_handler(self), *cmd_args)
        else:
            if line:
                self.terminal.write('No such command: %s' % cmd_name)
                self.terminal.nextLine()
            deferred = defer.Deferred()
            deferred.callback(None)

        @deferred
        def on_success(ret):
            self.print_prompt()

        @deferred
        def on_error(f):
            if not f.check(cmdline.ArgumentParsingError):
                f.raiseException()
            self.print_prompt()

        ret = defer.Deferred()
        deferred.addBoth(ret.callback)
        return ret

    def print_prompt(self):
        self.terminal.write(self.ps[self.pn])

    def insert_buffer(self, buf):
        """Insert some chars in the buffer at current cursor position."""
        lead, rest = self.lineBuffer[0:self.lineBufferIndex], self.lineBuffer[self.lineBufferIndex:]
        self.lineBuffer = lead + buf + rest
        self.lineBufferIndex += len(buf)

    def insert_text(self, text):
        """Insert some text at current cursor position and render it."""
        self.terminal.write(text)
        self.insert_buffer(list(text))

    @db.transact
    def handle_TAB(self):
        """Handle tab completion"""
        partial, rest, completions = completion.complete(self, self.lineBuffer, self.lineBufferIndex)

        if len(completions) == 1:
            space = '' if rest else ' '
            # handle quote closing
            if self.lineBuffer[self.lineBufferIndex - len(partial) - 1] == '"':
                space = '" '

            patch = completions[0][len(partial):] + space
            self.insert_text(patch)
        elif len(completions) > 1:
            common_prefix = os.path.commonprefix(completions)
            patch = common_prefix[len(partial):]
            self.insert_text(patch)

            # postpone showing list of possible completions until next tab
            if len(patch) == 0:
                self.terminal.nextLine()
                self.terminal.write(columnize(completions))
                self.print_prompt()
                self.terminal.write("".join(self.lineBuffer))
                if len(rest):
                    self.terminal.cursorBackward(len(rest))

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
        self.terminal.loseConnection()

    @property
    def ps(self):
        ps1 = '%s@%s:%s%s ' % ('user', 'oms', self._cwd(), '#')
        return [ps1, '... ']

    def _cwd(self):
        return self.make_path(self.path)

    @staticmethod
    def make_path(path):
        return '/'.join(path) or '/'
