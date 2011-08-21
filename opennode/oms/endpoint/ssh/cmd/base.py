from grokcore.component import queryOrderedSubscriptions
from twisted.internet import defer, reactor
from twisted.python.threadable import isInIOThread
from zope.component import queryAdapter

from opennode.oms.endpoint.ssh.cmdline import (ICmdArgumentsSyntax, IContextualCmdArgumentsSyntax,
                                               VirtualConsoleArgumentParser, ArgumentParsingError,
                                               PartialVirtualConsoleArgumentParser)
from opennode.oms.model.traversal import traverse_path
from opennode.oms.zodb import db


class Cmd(object):

    def __init__(self, protocol):
        self.protocol = protocol
        self.terminal = protocol.terminal

    @defer.inlineCallbacks
    def __call__(self, *args):
        """Subclasses should override this if you they need raw arguments."""
        parsed = yield defer.maybeDeferred(self.parse_args, args)
        yield self.execute(parsed)

    def execute(args):
        """Subclasses should override this if you they need parsed arguments."""

    @classmethod
    def _format_names(cls):
        if cls.aliases:
            return '{ %s }' % ' | '.join([cls.name] + cls.aliases)
        else:
            return cls.name

    def _make_arg_parser(self, parents, partial=False):
        parser_class = VirtualConsoleArgumentParser if not partial else PartialVirtualConsoleArgumentParser
        return parser_class(prog=self._format_names(), file=self.protocol.terminal, add_help=True, prefix_chars='-=', parents=parents)

    @defer.inlineCallbacks
    def _parent_parsers(self):
        parser_confs = queryOrderedSubscriptions(self, ICmdArgumentsSyntax)
        if ICmdArgumentsSyntax.providedBy(self):
            parser_confs.append(self)

        parsers = []
        for conf in parser_confs:
            p = yield conf.arguments()
            parsers.append(p)
        defer.returnValue(parsers)

    @defer.inlineCallbacks
    def arg_parser(self, partial=False):
        """Returns the argument parser for this command.

        Use partial=True if you want to tolerate incomplete last token
        and avoid executing the help action (e.g. during completion).

        """

        parents = yield self._parent_parsers()
        defer.returnValue(self._make_arg_parser(parents, partial=partial))

    @defer.inlineCallbacks
    def contextual_arg_parser(self, args, partial=False):
        """If the command is offers a contextual parser use it, otherwise
        fallback to the normal parser.

        Returns a deferred.
        """

        parser = yield self.arg_parser(partial=partial)

        contextual = queryAdapter(self, IContextualCmdArgumentsSyntax)
        if contextual:
            try:
                # We have to use a partial parser for this, because:
                # a) help printing is inhibited
                # b) it won't print errors
                # c) it will ignore mandatory arguments (e.g. if the context is not the only mandatory arg).
                partial_parser = yield self.arg_parser(partial=True)
                parsed, rest = partial_parser.parse_known_args(args)
            except ArgumentParsingError:
                # Fall back to uncontextualied parsed in case of parsing errors.
                # This happens when the "context defining" argument is declared as mandatory
                # but it's not yet present on the command line.
                defer.returnValue(parser)

            contextual_parser = yield contextual.arguments(parser, parsed, rest)
            defer.returnValue(contextual_parser)

        defer.returnValue(parser)

    @defer.inlineCallbacks
    def parse_args(self, args):
        """Parse command line arguments. Return a deferred."""

        parser = yield self.contextual_arg_parser(args)
        defer.returnValue(parser.parse_args(args))

    @property
    def path(self):
        return self.protocol.path
    @path.setter
    def path(self, path):
        self.protocol.path = path

    @property
    def obj_path(self):
        return self.protocol.obj_path
    @obj_path.setter
    def obj_path(self, path):
        self.protocol.obj_path = path

    @property
    def current_obj(self):
        return db.deref(self.obj_path[-1])

    def write(self, *args):
        """Ensure that all writes are serialized regardless if the command is executing in a another thread."""
        if not isInIOThread():
            reactor.callFromThread(self.terminal.write, *args)
        else:
            self.terminal.write(*args)

    def traverse_full(self, path):
        if path.startswith('/'):
            return traverse_path(db.get_root()['oms_root'], path[1:])
        else:
            return traverse_path(self.current_obj, path)

    def traverse(self, path):
        objs, unresolved_path = self.traverse_full(path)
        if not objs or unresolved_path:
            return None
        else:
            return objs[-1]
