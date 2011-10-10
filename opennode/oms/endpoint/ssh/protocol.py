import os
import re
import fnmatch
import itertools

from twisted.internet import defer
from twisted.python import log

from opennode.oms.endpoint.ssh import cmdline
from opennode.oms.endpoint.ssh.cmd import registry, completion
from opennode.oms.endpoint.ssh.colored_columnize import columnize
from opennode.oms.endpoint.ssh.terminal import InteractiveTerminal, BLUE
from opennode.oms.endpoint.ssh.tokenizer import CommandLineTokenizer, CommandLineSyntaxError
from opennode.oms.model.model.base import IContainer
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
        self.last_error = None

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

    @defer.inlineCallbacks
    def lineReceived(self, line):
        line = line.strip()

        try:
            command, cmd_args = yield self.parse_line(line)
        except CommandLineSyntaxError as e:
            self.terminal.write("Syntax error: %s\n" % (e.message))
            self.print_prompt()
            return

        deferred = defer.maybeDeferred(command, *cmd_args)

        @deferred
        def on_error(f):
            if not f.check(cmdline.ArgumentParsingError):
                self.terminal.write("Command returned an unhandled error: %s\n" % f.getErrorMessage())
                self.last_error = (line, f)
                log.msg("Got exception executing '%s': %s" % self.last_error)
                self.terminal.write("type last_error for more details\n")

        deferred.addBoth(lambda *_: self.print_prompt())

    @db.transact
    def parse_line(self, line):
        """Returns a command instance and parsed cmdline argument list.

        TODO: Shell expansion should be handled here.

        """

        cmd_name, cmd_args = line.partition(' ')[::2]
        command_cls = registry.get_command(cmd_name)

        tokenized_cmd_args = self.expand(self.tokenizer.tokenize(cmd_args.strip()))

        return command_cls(self), tokenized_cmd_args

    def expand(self, tokens):
        return list(itertools.chain.from_iterable(map(self.expand_token, tokens)))

    def expand_token(self, token):
        if re.match('.*[*[\]].*', os.path.basename(token)):
            base = os.path.dirname(token)

            if os.path.isabs(base):
                objs, unres = traverse_path(db.get_root()['oms_root'], base[1:])
            else:
                objs, unres = traverse_path(db.deref(self.obj_path[-1]), base)

            # Only if intermediate path resolves.
            if objs:
                current_obj = objs[-1]
                if IContainer.providedBy(current_obj):
                    filtered = [os.path.join(base, i) for i in fnmatch.filter(current_obj.listnames(), os.path.basename(token))]
                    # Bash behavior: if expansion doesn't provide results then pass the glob pattern to the command.
                    if filtered:
                        return filtered
        return [token]

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
            # Avoid space after '/' for functionality.
            for i in ('=', '/'):
                if completions[0].endswith(i):
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
                completions = [self.colorize(BLUE, item) if item.endswith('/') else item for item in completions]
                self.terminal.write(columnize(completions, self.width))
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
