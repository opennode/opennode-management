import fnmatch
import itertools
import os
import re
import sys
import traceback

from grokcore.component import Subscription, implements, context
from twisted.conch.insults.insults import ServerProtocol
from twisted.internet import defer
from twisted.python import log
from zope.security.interfaces import ForbiddenAttribute, Unauthorized

from opennode.oms.config import get_config
from opennode.oms.endpoint.ssh import cmdline
from opennode.oms.endpoint.ssh.cmd import registry, completion, commands
from opennode.oms.endpoint.ssh.colored_columnize import columnize
from opennode.oms.endpoint.ssh.terminal import InteractiveTerminal, BLUE, CYAN, GREEN, CTRL_C
from opennode.oms.endpoint.ssh.tokenizer import CommandLineTokenizer, CommandLineSyntaxError
from opennode.oms.model.model.base import IContainer
from opennode.oms.model.model.bin import ICommand
from opennode.oms.model.model.proc import Proc
from opennode.oms.security.interaction import new_interaction
from opennode.oms.zodb import db
from opennode.oms.zodb.extractors import IContextExtractor


def protocolInlineCallbacks(fun):
    """Executes protocol async callbacks while buffering next keystrokes
    during the execution of the callback. After the callback finishes
    the buffered keystrokes will be replayed back, but currently
    only non-special characters are replayed, since special characters could
    trigger a reentrant here which would inject keystrokes out of order.
    """
    @defer.inlineCallbacks
    def wrapper(self, *args, **kwargs):
        try:
            old_sub_protocol = self.sub_protocol
            if not old_sub_protocol:
                self.sub_protocol = CallbackExecutionSubProtocol()

            yield defer.inlineCallbacks(fun)(self, *args, **kwargs)
        except Exception as e:
            if get_config().getboolean('debug', 'print_exceptions'):
                traceback.print_exc()
            print "[protocol] got exception while %s: %s" %  (fun, e)

        execution_sub_protocol = self.sub_protocol
        self.sub_protocol = old_sub_protocol
        for (key, mod) in execution_sub_protocol.buffer:
            if key not in self.keyHandlers.keys():
                self.keystrokeReceived(key, mod)

    return wrapper


class CallbackExecutionSubProtocol(object):
    def __init__(self):
        self.buffer = []

    def keystrokeReceived(self, keyID, mod):
        self.buffer.append((keyID, mod))


class OmsShellProtocol(InteractiveTerminal):
    """The OMS virtual console over SSH.

    Accepts lines of input and writes them back to its connection.  If
    a line consisting solely of "quit" is received, the connection
    is dropped.

    """

    def __init__(self):
        super(OmsShellProtocol, self).__init__()
        self.path = ['']
        self.last_error = None
        self.environment = {'PATH': '.:./actions:/bin'}
        self.path_stack = []
        self.sub_protocol = None
        self.principal = None
        self.use_security_proxy = get_config().getboolean('auth', 'security_proxy_omsh')

        @defer.inlineCallbacks
        def _get_obj_path():
            self.obj_path = yield db.ro_transact(lambda: [db.ref(db.get_root()['oms_root'])])()

        self.get_object_path_deferred = _get_obj_path()

        self.tokenizer = CommandLineTokenizer()

    @defer.inlineCallbacks
    def ensure_initialized(self):
        yield self.get_object_path_deferred

    def logged_in(self, principal):
        """Invoked when the principal which opened this session is known"""

        self.principal = principal
        self.interaction = new_interaction(principal.id)
        self.tid = Proc.register(None, self, '/bin/omsh', principal=principal)

        self.terminalSizeAfterLogin()

    def connectionMade(self):
        super(OmsShellProtocol, self).connectionMade()

    def close_connection(self):
        Proc.unregister(self.tid)
        super(OmsShellProtocol, self).close_connection()

    def dataReceived(self, data):
        # some sub protocols need raw data, because `keystrokeReceived`
        # reinterprets all special chars (like arrows etc) and there is no way
        # to get back to the original escape sequences.
        if self.sub_protocol and hasattr(self.sub_protocol, 'dataReceived'):
            return self.sub_protocol.dataReceived(data)
        self.terminal._orig_dataReceived(data)

    def keystrokeReceived(self, keyID, modifier):
        (self.sub_protocol or super(OmsShellProtocol, self)).keystrokeReceived(keyID, modifier)

    def exit_sub_protocol(self):
        self.sub_protocol = None
        self.print_prompt()

    @defer.inlineCallbacks
    def lineReceived(self, line):
        try:
            yield self.spawn_commands(line)
        finally:
            self._command_completed()

    @defer.inlineCallbacks
    def spawn_commands(self, line):
        yield self.ensure_initialized()

        # XXX: handle ; chars in quotes and comments
        for command in line.split(';'):
            yield self.spawn_command(command)

    @defer.inlineCallbacks
    def spawn_command(self, line):
        line = line.strip()

        try:
            command, cmd_args = yield self.parse_line(line)
        except CommandLineSyntaxError as e:
            self.terminal.write("Syntax error: %s\n" % (e.message))
            self.print_prompt()
            return
        except Exception as e:
            log.msg("Got exception parsing '%s': %s" % (line, sys.exc_info()))
            self.terminal.write(''.join(traceback.format_exception(*sys.exc_info())))
            return

        self.sub_protocol = CommandExecutionSubProtocol(self)
        deferred = defer.maybeDeferred(command, *cmd_args)
        Proc.register(deferred, self, line, self.tid)

        try:
            yield deferred
        except cmdline.ArgumentParsingError:
            pass
        except Unauthorized as e:
            msg = e
            if isinstance(e.message, tuple) and len(e.message) == 3:
                msg = "accessing %s's attribute '%s' requires @%s right" % e.message
            self.terminal.write("Permission denied: %s\n" % msg)
        except Exception as e:
            self.terminal.write("Command returned an unhandled error: %s\n" % e)
            self.last_error = (line, sys.exc_info())
            log.msg("Got exception executing '%s': %s" % self.last_error)

            if get_config().getboolean('debug', 'print_exceptions'):
                traceback.print_tb(self.last_error[1][2])

            self.terminal.write("type last_error for more details\n")

    def _command_completed(self, *args):
        self.print_prompt()
        if self.sub_protocol:
            buffer = self.sub_protocol.buffer
            self.sub_protocol = None

            for (key, mod) in buffer or ():
                if key not in self.keyHandlers.keys():
                    self.keystrokeReceived(key, mod)

    @db.ro_transact
    def parse_line(self, line):
        """Returns a command instance and parsed cmdline argument list.

        TODO: Shell expansion should be handled here.

        """

        cmd_name, cmd_args = line.partition(' ')[::2]
        command_cls = self.get_command_class(cmd_name)
        command = command_cls(self)

        tokenized_cmd_args = self.expand(command, self.tokenizer.tokenize(cmd_args.strip()))

        return command, tokenized_cmd_args

    def get_command_class(self, name):
        # NOTE: used to leverage the 'traverse()' method which take into consideration
        # path handling quirks for relative paths
        dummy = commands.NoCommand(self)
        for d in self.environment['PATH'].split(':'):
            effective_dir = name
            if not os.path.isabs(name):
                effective_dir = os.path.join(d, name)
            try:
                command = dummy.traverse(effective_dir)
                if ICommand.providedBy(command):
                    return command.cmd
            except ForbiddenAttribute:
                # skip command paths where we don't have access
                pass

        # NOTE: retained temporarily because it contains inner class
        return registry.get_command(name)

    def expand(self, command, tokens):
        return list(itertools.chain.from_iterable([self.expand_token(command, i) for i in tokens]))

    def expand_token(self, command, token):
        if re.match('.*[*[\]].*', os.path.basename(token)):
            base = os.path.dirname(token)

            current_obj = command.traverse(base)

            # Only if intermediate path resolves.
            if current_obj:
                if IContainer.providedBy(current_obj):
                    filtered = [os.path.join(base, i) for i in fnmatch.filter(current_obj.listnames(), os.path.basename(token))]
                    # Bash behavior: if expansion doesn't provide results then pass the glob pattern to the command.
                    if filtered:
                        return filtered
        return [token]

    @protocolInlineCallbacks
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

            # Drop @, *, half hack
            for i in ('@', '*'):
                if patch.endswith(i + ' '):
                    patch = patch.rstrip(i + ' ') + ' '

            self.insert_text(patch)
        elif len(completions) > 1:
            common_prefix = os.path.commonprefix(completions)
            patch = common_prefix[len(partial):]
            self.insert_text(patch)

            # postpone showing list of possible completions until next tab
            if not patch:
                self.terminal.nextLine()
                _, _, completions = yield completion.complete(self, self.lineBuffer, self.lineBufferIndex, display=True)

                # reorder optional values at end for readability
                required = []
                optional = []
                for comp in completions:
                    (optional if comp.startswith('[') else required).append(comp)

                completions = required + optional

                completions = [self.colorize(self._completion_color(item), item) for item in completions]
                self.terminal.write(columnize(completions, self.width))
                self.drawInputLine()
                if len(rest):
                    self.terminal.cursorBackward(len(rest))

    def _completion_color(self, completion):
        if completion.endswith('/'):
            return BLUE
        elif completion.endswith('@'):
            return CYAN
        elif completion.endswith('*'):
            return GREEN
        else:
            return None

    @property
    def hist_file_name(self):
        return os.path.expanduser('~/.oms_history')

    @property
    def ps(self):
        user = self.principal.id if self.principal else 'user'
        ps1 = '%s@%s:%s%s ' % (user, 'oms', self._cwd(), '#')
        return [ps1, '... ']

    def _cwd(self):
        return self.make_path(self.path)

    @staticmethod
    def make_path(path):
        return '/'.join(path) or '/'

    def handle_EOF(self):
        (self.sub_protocol or super(OmsShellProtocol, self)).handle_EOF()


class CommandExecutionSubProtocol(object):
    def __init__(self, parent):
        self.parent = parent
        self.buffer = []

    def handle_EOF(self):
        pass

    def _echo(self, keyID, mod):
        """Echoes characters on terminal like on unix (special chars etc)"""
        ch = keyID
        if isinstance(keyID, str):
            if ord(keyID) == 127:
                ch = '^H'
            if ord(keyID) < 32 and keyID != '\r':
                ch = '^' + chr(ord('A') + ord(keyID) - 1)
            self.parent.terminal.write(ch)
            if keyID in ('\r', CTRL_C):
                self.parent.terminal.write('\n')

    def keystrokeReceived(self, keyID, mod):
        self._echo(keyID, mod)

        # HACK: poor man's interrupt
        if keyID == CTRL_C:
            return self.parent.exit_sub_protocol()

        self.buffer.append((keyID, mod))


class ProtocolContextExtractor(Subscription):
    implements(IContextExtractor)
    context(OmsShellProtocol)

    def get_context(self):
        return {'interaction': self.context.interaction}


# HACK: Monkey patch
# TODO: handle this with custom ServerProtocol
def dataReceived(self, data):
    return self.terminalProtocol.dataReceived(data)

ServerProtocol._orig_dataReceived = ServerProtocol.dataReceived

ServerProtocol.dataReceived = dataReceived
