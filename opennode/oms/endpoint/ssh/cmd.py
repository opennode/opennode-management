import transaction
import zope.schema
from columnize import columnize
from grokcore.component import implements, context, Adapter, Subscription, baseclass, order, queryOrderedSubscriptions
from twisted.internet import defer, reactor
from twisted.python.failure import Failure
from twisted.python.threadable import isInIOThread
from zope.component import provideSubscriptionAdapter, queryAdapter
import argparse

from opennode.oms.endpoint.ssh.cmdline import ICmdArgumentsSyntax, IContextualCmdArgumentsSyntax, GroupDictAction, VirtualConsoleArgumentParser, PartialVirtualConsoleArgumentParser, ArgumentParsingError
from opennode.oms.model.form import apply_raw_data
from opennode.oms.model.model import creatable_models
from opennode.oms.model.model.base import IContainer
from opennode.oms.model.traversal import traverse_path
from opennode.oms.util import get_direct_interfaces, get_direct_interface
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

    @defer.inlineCallbacks
    def parent_parsers(self):
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

        parents = yield  self.parent_parsers()
        defer.returnValue(self.make_arg_parser(parents, partial=partial))

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

    @db.transact
    def execute(self, args):
        if not args.path:
            self.path = [self.path[0]]
            self.obj_path = [self.obj_path[0]]
            return

        self._do_traverse(args.path)

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
            self._do_ls(self.current_obj)

    def _do_ls(self, obj, path=None):
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

    implements(ICmdArgumentsSyntax)

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('path')
        return parser

    def _schema(self, obj):
        schemas = get_direct_interfaces(obj)

        if len(schemas) != 1:
            return
        return schemas[0]

    @db.transact
    def execute(self, args):
        # Argparse doesn't currently return objects, but only paths
        # so we have to manually traverse it.
        obj = self.traverse(args.path)
        if not obj:
            self.write("No such object: %s\n" % args.path)
            return

        # Dynamic arguments will end up in the `keywords` arg
        # thanks to GroupDictAction, but it's not guaranteed that
        # at least one argument exists.
        raw_data = getattr(args, 'keywords', {})

        schema = self._schema(obj)
        if not schema:
            self.write("No schema found for object: %s\n" % args.path)
            return

        if args.verbose:
            for key, value in raw_data.items():
                self.write("Setting %s=%s\n" % (key, value))

        errors = apply_raw_data(raw_data, schema, obj)

        if errors:
            for key, error in errors:
                msg = error.doc().encode('utf8')
                self.write("%s: %s\n" % (key, msg) if key else "%s\n" % msg)

        transaction.commit()


class SetCmdDynamicArguments(Adapter):
    """Dynamically creates the key=value arguments for the `set` command
    based upon the object being edited.
    """

    implements(IContextualCmdArgumentsSyntax)
    context(cmd_set)

    @db.transact
    def arguments(self, parser, args, rest):
        # sanity checks
        obj = self.context.traverse(args.path)
        if not obj:
            return parser

        schema = self.context._schema(obj)
        if not schema:
            return parser

        # Adds dynamically generated keywords to the parser taking them from the object's schema.
        # Handles choices and the int type.
        for name, field in zope.schema.getFields(schema).items():
            choices = None
            type = None
            if isinstance(field, zope.schema.Choice):
                choices = [voc.value.encode('utf-8') for voc in field.vocabulary]
            if isinstance(field, zope.schema.Int):
                type = int

            parser.add_argument('=' + name, type=type, action=GroupDictAction, group='keywords', help=field.title.encode('utf8'), choices=choices)

        return parser


provideSubscriptionAdapter(CommonArgs, adapts=[cmd_set])


class cmd_mk(Cmd):
    implements(ICmdArgumentsSyntax)

    @db.transact
    def arguments(self):
        parser = VirtualConsoleArgumentParser()

        obj = self.current_obj
        choices = creatable_models.keys()

        # TODO: Handle interface containment, if we'll ever have it.
        if getattr(obj, '__contains__', None):
            for name, cls in creatable_models.items():
                if cls == obj.__contains__:
                    choices = [name]
                    break

        parser.add_argument('type', choices=choices, help="object type to be created")
        return parser

    @db.transact
    def execute(self, args):
        model_cls = creatable_models.get(args.type)

        # TODO: this hack was made to make the test run.
        # Perhaps we should have a better factory for creatable object
        # (e.g something that doesn't require reflection)
        # like the apply_raw_data
        # NOTE: arparser already convers int parameters according to the zope.schema.
        # but we might want to create nodes also from other APIs, so something like apply_raw_data would fit.
        import inspect
        obj = model_cls(*[args.keywords.get(arg_name, None) for arg_name in inspect.getargspec(model_cls.__init__).args[1:]])

        self.current_obj.add(obj)


class MkCmdDynamicArguments(Adapter):
    """Dynamically creates the key=value arguments for the `mk` command
    based upon the type being created.
    """

    implements(IContextualCmdArgumentsSyntax)
    context(cmd_mk)

    def arguments(self, parser, args, rest):
        model_cls = creatable_models.get(args.type)
        schema = get_direct_interface(model_cls)

        for name, field in zope.schema.getFields(schema).items():
            choices = None
            type = None
            if isinstance(field, zope.schema.Choice):
                choices = [voc.value.encode('utf-8') for voc in field.vocabulary]
            if isinstance(field, zope.schema.Int):
                type = int

            parser.add_argument('=' + name, required=True, type=type, action=GroupDictAction, group='keywords', help=field.title.encode('utf8'), choices=choices)

        return parser

class cmd_help(Cmd):
    """Get the names of the commands from this modules and prints them out."""

    def execute(self, args):
        self.write("valid commands: %s\n" % (', '.join(commands().keys())))


class cmd_quit(Cmd):
    """Quits the console."""

    def execute(self, args):
        self.protocol.close_connection()

class cmd_last_error(Cmd):
    """Prints out the last error.
    Useful for devs, and users reporting to issue tracker.
    (Inspired by xsbt)

    """

    def execute(self, args):
        if self.protocol.last_error:
            cmdline, failure = self.protocol.last_error
            self.write("Error executing '%s': %s" % (cmdline, failure))


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

    UndefinedCommand.name = name

    return commands().get(name, UndefinedCommand)
