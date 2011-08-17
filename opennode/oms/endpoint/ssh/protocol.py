import os

from columnize import columnize
from twisted.internet import defer

from opennode.oms.endpoint.ssh import cmd, completion, cmdline
from opennode.oms.endpoint.ssh.terminal import InteractiveTerminal
from opennode.oms.endpoint.ssh.tokenizer import CommandLineTokenizer, CommandLineSyntaxError
from opennode.oms.zodb import db


class OmsSshProtocol(InteractiveTerminal):
    """The OMS virtual console over SSH.

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

    def lineReceived(self, line):
        line = line.strip()

        try:
            command, cmd_args = self.parse_line(line)
        except CommandLineSyntaxError as e:
            self.terminal.write("Syntax error: %s\n" % (e.message))
            self.print_prompt()
            return

        deferred = defer.maybeDeferred(command, *cmd_args)

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
        """Inserts some chars in the buffer at the current cursor position."""
        lead, rest = self.lineBuffer[0:self.lineBufferIndex], self.lineBuffer[self.lineBufferIndex:]
        self.lineBuffer = lead + buf + rest
        self.lineBufferIndex += len(buf)

    def insert_text(self, text):
        """Inserts some text at the current cursor position and renders it."""
        self.terminal.write(text)
        self.insert_buffer(list(text))

    def parse_line(self, line):
        """Returns a command instance and parsed cmdline argument list.

        TODO: Shell expansion should be handled here.

        """

        cmd_name, cmd_args = line.partition(' ')[::2]
        command_cls = cmd.get_command(cmd_name)

        tokenized_cmd_args = self.tokenizer.tokenize(cmd_args.strip())

        return command_cls(self), tokenized_cmd_args

    @defer.inlineCallbacks
    def handle_TAB(self):
        """Handles tab completion."""
        partial, rest, completions = yield completion.complete(self, self.lineBuffer, self.lineBufferIndex)

        if len(completions) == 1:
            space = '' if rest else ' '
            # handle quote closing
            if self.lineBuffer[self.lineBufferIndex - len(partial) - 1] == '"':
                space = '" '
            # Avoid space after '=' just for aestetics.
            if completions[0].endswith('='):
                space = ''

            patch = completions[0][len(partial):] + space
            self.insert_text(patch)
        elif len(completions) > 1:
            common_prefix = os.path.commonprefix(completions)
            patch = common_prefix[len(partial):]
            self.insert_text(patch)

            # postpone showing list of possible completions until next tab
            if not patch:
                self.terminal.nextLine()
                self.terminal.write(columnize(completions))
                self.drawInputLine()
                if len(rest):
                    self.terminal.cursorBackward(len(rest))


    @property
    def hist_file_name(self):
        return os.path.expanduser('~/.oms_history')

    @property
    def ps(self):
        ps1 = '%s@%s:%s%s ' % ('user', 'oms', self._cwd(), '#')
        return [ps1, '... ']

    def _cwd(self):
        return self.make_path(self.path)

    @staticmethod
    def make_path(path):
        return '/'.join(path) or '/'
