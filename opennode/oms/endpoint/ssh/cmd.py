import transaction
import zope.schema
from columnize import columnize
from grokcore.component import implements, context, Subscription, baseclass, order, queryOrderedSubscriptions
from twisted.internet import defer, reactor
from twisted.python.failure import Failure
from twisted.python.threadable import isInIOThread
from zope.component import provideSubscriptionAdapter, queryAdapter
import argparse

from opennode.oms.endpoint.ssh.cmdline import ICmdArgumentsSyntax, IContextualCmdArgumentsSyntax, VirtualConsoleArgumentParser, PartialVirtualConsoleArgumentParser
from opennode.oms.model.form import apply_raw_data
from opennode.oms.model.model import creatable_models
from opennode.oms.model.model.base import IContainer
from opennode.oms.model.traversal import traverse_path
from opennode.oms.util import get_direct_interfaces
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

    def make_arg_parser(self, parents, partial=False):
        parser_class = VirtualConsoleArgumentParser if not partial else PartialVirtualConsoleArgumentParser
        return parser_class(prog=self.name, file=self.protocol.terminal, add_help=True, prefix_chars='-=', parents=parents)

    def parent_parsers(self):
        parser_confs = queryOrderedSubscriptions(self, ICmdArgumentsSyntax)
        if ICmdArgumentsSyntax.providedBy(self):
            parser_confs.append(self)
        return [conf.arguments() for conf in parser_confs]

    def arg_parser(self, partial=False):
        """Returns the argument parser for this command.

        Use partial=True if you want to tolerate incomplete last token
        and avoid executing the help action (e.g. during completion).

        """

        return self.make_arg_parser(self.parent_parsers(), partial=partial)

    def contextual_arg_parser(self, args, partial=False):
        """If the command is offers a contextual parser use it, otherwise
        fallback to the normal parser.

        Returns a deferred.
        """

        parser = self.arg_parser(partial=partial)

        contextual = queryAdapter(self, IContextualCmdArgumentsSyntax)
        if contextual:
            parsed, rest = parser.parse_known_args(args)
            return defer.maybeDeferred(contextual.arguments, parser, parsed, rest)

        return defer.succeed(parser)

    @defer.inlineCallbacks
    def parse_args(self, args):
        """Parse command line arguments. Return a deferred."""

        parser = yield self.contextual_arg_parser(args)
        defer.returnValue(parser.parse_args(args))

    @property
    def name(self):
        """The name of the current command.

        If the command name is not in the form of `cmd_[name]`, it should be defined explicitly.

        """
        assert self.__class__.__name__.startswith('cmd_')
        return self.__class__.__name__[4:]

    @property
    def path(self):
        return self.protocol.path
    @path.setter
    def _set_path(self, path):
        self.protocol.path = path

    @property
    def obj_path(self):
        return self.protocol.obj_path
    @obj_path.setter
    def _set_obj_path(self, path):
        self.protocol.obj_path = path

    @property
    def current_obj(self):
        return db.deref(self.obj_path[-1])

    def current_path(self):
        return self.path[-1]

    def write(self, *args):
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


class NoCommand(Cmd):
    """Represents the fact that there is no command yet."""

    name = 'no-command'

    def __call__(self, *args):
        """Just do nothing."""


class CommonArgs(Subscription):
    """Just an example of common args, not actually sure that -v is needed in every command."""
    implements(ICmdArgumentsSyntax)
    baseclass()
    order(-1)

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('-v', '--verbose', action='count', help="be verbose, use it multiple times to increase verbosity")
        return parser


class cmd_cd(Cmd):
    implements(ICmdArgumentsSyntax)

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('path', nargs='?')
        return parser

    def execute(self, args):
        if not args.path:
            self.protocol.path = [self.path[0]]
            self.protocol.obj_path = [self.obj_path[0]]
            return

        deferred = self._do_traverse(args.path)

        @deferred
        def on_error(f):
            f.printDetailedTraceback(self.terminal)
            self.write('\n')

        d = defer.Deferred()
        deferred.addBoth(lambda *args: d.callback(None))
        return d

    @db.transact
    def _do_traverse(self, path):
        objs, unresolved_path = self.traverse_full(path)

        if not objs or unresolved_path:
            self.write('No such object: %s\n' % path)
            return

        if not IContainer.providedBy(objs[-1]):
            self.write('Cannot cd to a non-container\n')
            return

        # The following algorithm works for both up-the-tree,
        # down-the-tree and mixed traversals. So all of the following
        # arguments to the 'cd' command work out as expected:
        #     foo/bar # foo/./../foo ../foo/../.  ../.././foo
        for obj in objs:
            ref = db.ref(obj)
            try:
                # Try to find the object in the current path:
                overlap = self.obj_path.index(ref)
            except ValueError:
                # ... if not found, add it:
                self.obj_path.append(ref)
                self.path.append(obj.__name__)
            else:
                # ... otherwise remove everything that follows it:
                self.obj_path[overlap+1:] = []
                self.path[overlap+1:] = []


class cmd_ls(Cmd):
    implements(ICmdArgumentsSyntax)

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('-l', action='store_true')
        parser.add_argument('-d', help="dummy param which takes a value")
        parser.add_argument('paths', nargs='*')
        return parser

    @db.transact
    def execute(self, args):
        self.opts_long = args.l

        if args.paths:
            for path in args.paths:
                obj = self.traverse(path)
                if not obj:
                    self.write('No such object: %s\n' % path)
                else:
                    self._do_ls(obj, path)
        else:
            try:
                self._do_ls(self.current_obj, self.current_path)
            except:
                print Failure().printDetailedTraceback(self.terminal)

    def _do_ls(self, obj, path):
        if self.opts_long:
            if IContainer.providedBy(obj):
                for item in obj.listcontent():
                    self.write(('%s\t%s\n' % (item.__name__, ':'.join(item.nicknames))).encode('utf8'))
            else:
                self.write(('%s\t%s\n' % (obj.__name__, ':'.join(obj.nicknames))).encode('utf8'))
        else:
            if IContainer.providedBy(obj):
                items = list(obj.listnames())
                if items:
                    output = columnize(items, displaywidth=self.protocol.width)
                    self.write(output)
            else:
                self.write('%s\n' % path)

provideSubscriptionAdapter(CommonArgs, adapts=[cmd_ls])


class cmd_pwd(Cmd):
    def execute(self, args):
        self.write('%s\n' % self.protocol._cwd())


class cmd_cat(Cmd):
    implements(ICmdArgumentsSyntax)

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('paths', nargs='+')
        return parser

    @db.transact
    def execute(self, args):
        for path in args.paths:
            obj = self.traverse(path)
            if not obj:
                self.write("No such object: %s\n" % path)
            else:
                self._do_cat(obj)

    def _do_cat(self, obj):
        schemas = get_direct_interfaces(obj)
        if len(schemas) != 1:
            self.write("Unable to create a printable representation.\n")
            return
        schema = schemas[0]

        fields = zope.schema.getFieldsInOrder(schema)
        data = {}
        for name, field in fields:
            key = field.description or field.title
            key = key.encode('utf8')
            data[key] = field.get(obj)

        if data:
            max_key_len = max(len(key) for key in data)
            for key, value in sorted(data.items()):
                self.write("%s\t%s\n" % ((key + ':').ljust(max_key_len),
                                         str(value).encode('utf8')))


class cmd_set(Cmd):

    @db.transact
    def __call__(self, *args):
        if not args:
            self._usage()
            return

        # compat: new tokenizer splits key=value into ["=key", "value"]
        # in order to make it easier to declare keys as argparse options
        args = self.fixup_args(args)

        path = args[0]
        obj = self.traverse(path)
        if not obj:
            self.write("No such object: %s\n" % path)
            return

        raw_data = {}

        attrs = args[1:]

        if not all('=' in pair for pair in attrs):
            self._usage()
            return

        for pair in attrs:
            key, value = pair.split('=', 1)
            raw_data[key] = value

        schemas = get_direct_interfaces(obj)
        if len(schemas) != 1:
            self.write("No schema found for object: %s" % path)
            return
        schema = schemas[0]
        errors = apply_raw_data(raw_data, schema, obj)

        if errors:
            for key, error in errors:
                msg = error.doc().encode('utf8')
                self.write("%s: %s\n" % (key, msg) if key else "%s\n" % msg)

        transaction.commit()

    @staticmethod
    def fixup_args(args):
        last = args[0]
        new_args = []
        for arg in args[1:]:
            if last and last.startswith('='):
                new_args.append(last[1:] + '=' + arg)
                last = None
            else:
                if last:
                    new_args.append(last)
                last = arg
        if last:
            if last.startswith('='):
                new_args.append(last[1:] + '=')
            else:
                new_args.append(last)

        return new_args

    def _usage(self):
        self.write("Usage: set obj key=value [key=value ..]\n\n"
                   "Sets attributes on objects.\n"
                   "If setting or parsing of one of the attributes fails, "
                   "the operation is cancelled and the object unchanged.\n")


class cmd_mk(Cmd):

    def __call__(self, *args):
        if not args:
            self._usage()
            return

        type_name = args[0]
        model_cls = creatable_models.get(type_name)
        if model_cls:
            self.write("No such type: %s\n" % type_name)
            return

        obj = model_cls()

    def _usage(self):
        self.write("Usage: mk type key=value [key=value ..]\n\n"
                   "Creates objects of given type.\n"
                   "If setting or parsing of one of the attributes fails, "
                   "the operation is cancelled and no object is created.\n")


class cmd_help(Cmd):
    """Get the names of the commands from this modules and prints them out."""

    def execute(self, args):
        self.write("valid commands: %s\n" % (', '.join(commands().keys())))


class cmd_quit(Cmd):
    """Quits the console."""

    def execute(self, args):
        self.protocol.close_connection()


def commands():
    """Create a map of command names to command objects."""
    # TODO: We should use martian to create a directive to register
    # commands by name.  This would rid us of the need to follow a
    # naming convention for Cmd subclasses, and the need to have a
    # dynamic name property. It would also enable us to avoid the
    # special casing with NoCommand in get_command.
    return dict((name[4:], cmd) for name, cmd in globals().iteritems() if name.startswith('cmd_'))


def get_command(name):
    """Returns the command class for a given name.

    Returns NoCommand if the name is empty.
    Returns UnknownCommand if the command does not exist.

    """

    # TODO: Remove this once we have the better command registration (described above).
    if not name:
        return NoCommand

    # TODO: Is this approach needed as opposed to handling it
    # upstream? Is this a result of over engineering?
    class UndefinedCommand(Cmd):
        def __call__(self, *args):
            self.terminal.write("No such command: %s\n" % name)

    return commands().get(name, UndefinedCommand)
