import inspect

import transaction
import zope.schema
from grokcore.component import implements, context, Adapter, Subscription, baseclass, order
from twisted.internet import defer
from zope.component import provideSubscriptionAdapter

from opennode.oms.endpoint.ssh.cmd import registry
from opennode.oms.endpoint.ssh.cmd.base import Cmd
from opennode.oms.endpoint.ssh.cmd.directives import command, alias
from opennode.oms.endpoint.ssh.cmdline import ICmdArgumentsSyntax, IContextualCmdArgumentsSyntax, GroupDictAction, VirtualConsoleArgumentParser
from opennode.oms.endpoint.ssh.colored_columnize import columnize
from opennode.oms.endpoint.ssh.terminal import BLUE
from opennode.oms.model.form import ApplyRawData
from opennode.oms.model.model import creatable_models
from opennode.oms.model.model.base import IContainer
from opennode.oms.util import get_direct_interfaces
from opennode.oms.zodb import db


class NoCommand(Cmd):
    """Represents the fact that there is no command yet."""

    command('')

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


class ChangeDirCmd(Cmd):
    implements(ICmdArgumentsSyntax)

    command('cd')

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


class ListDirContentsCmd(Cmd):
    implements(ICmdArgumentsSyntax)

    command('ls')

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
        def pretty_name(item):
            if IContainer.providedBy(item):
                return self.protocol.colorize(BLUE, item.__name__ + '/')
            else:
                return item.__name__

        def sorted_obj_list():
            return sorted(obj.listcontent(), key=lambda o: o.__name__)

        if self.opts_long:
            def nick(item):
                return getattr(item, 'nicknames', [])

            if IContainer.providedBy(obj):
                for subobj in sorted_obj_list():
                    self.write(('%s\t%s\n' % (pretty_name(subobj), ':'.join(nick(subobj)))).encode('utf8'))
            else:
                self.write(('%s\t%s\n' % (pretty_name(obj), ':'.join(nick(obj)))).encode('utf8'))
        else:
            if IContainer.providedBy(obj):
                items = [pretty_name(subobj) for subobj in sorted_obj_list()]
                if items:
                    output = columnize(items, displaywidth=self.protocol.width)
                    self.write(output)
            else:
                self.write('%s\n' % path)

provideSubscriptionAdapter(CommonArgs, adapts=(ListDirContentsCmd, ))


class PrintWorkDirCmd(Cmd):
    command('pwd')

    def execute(self, args):
        self.write('%s\n' % self.protocol._cwd())


class CatObjectCmd(Cmd):
    implements(ICmdArgumentsSyntax)

    command('cat')

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


class RemoveCmd(Cmd):
    """Deletes an object."""
    implements(ICmdArgumentsSyntax)

    command('rm')

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
                continue

            del obj.__parent__[obj.__name__]

        transaction.commit()


class MoveCmd(Cmd):
    """Moves an object."""
    implements(ICmdArgumentsSyntax)

    command('mv')

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('paths', nargs=2)
        return parser

    @db.transact
    def execute(self, args):
        src_path, dest_path = args.paths

        src = self.traverse(src_path)
        dest = self.traverse(dest_path)

        if not IContainer.providedBy(dest):
            self.write("Destination %s has to be a container.\n" % dest)
            return

        # `add` will take care of removing the old parent.
        dest.add(src)

        transaction.commit()


class SetAttrCmd(Cmd):
    implements(ICmdArgumentsSyntax)

    command('set')

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

        if args.verbose:
            for key, value in raw_data.items():
                self.write("Setting %s=%s\n" % (key, value))

        form = ApplyRawData(raw_data, obj)

        if not form.errors:
            form.apply()
        else:
            for key, error in form.errors:
                msg = error.doc().encode('utf8')
                self.write("%s: %s\n" % (key, msg) if key else "%s\n" % msg)

        transaction.commit()


class SetCmdDynamicArguments(Adapter):
    """Dynamically creates the key=value arguments for the `set` command
    based upon the object being edited.

    """

    implements(IContextualCmdArgumentsSyntax)
    context(SetAttrCmd)

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

            parser.add_argument('=' + name, type=type, action=GroupDictAction,
                                group='keywords', help=field.title.encode('utf8'), choices=choices)

        return parser


provideSubscriptionAdapter(CommonArgs, adapts=(SetAttrCmd, ))


class CreateObjCmd(Cmd):
    implements(ICmdArgumentsSyntax)

    command('mk')
    alias('create')

    @db.transact
    def arguments(self):
        parser = VirtualConsoleArgumentParser()

        obj = self.current_obj

        choices = []
        if getattr(obj, '__contains__', None):
            for name, cls in creatable_models.items():
                if obj.can_contain(cls):
                    choices.append(name)

        # TODO: are we sure we want to show the whole list in case nothing matches?
        # I think it can only happen due to incomplete declaration of our models (which should be a bug)
        # but when we'll include security, there might be some models which the user simply cannot create
        # so the list could legally be empty.
        # -- ...so why have this check?
        if not choices:
            choices = creatable_models.keys()

        parser.add_argument('type', choices=choices, help="object type to be created")
        return parser

    @db.transact
    def execute(self, args):
        model_cls = creatable_models.get(args.type)

        form = ApplyRawData(args.keywords, model=model_cls)
        if not form.errors:
            obj = form.create()
            obj_id = self.current_obj.add(obj)
            self.write("%s\n" % obj_id)
        else:
            for key, error in form.errors:
                msg = error.doc().encode('utf8')
                self.write("%s: %s\n" % (key, msg) if key else "%s\n" % msg)


class MkCmdDynamicArguments(Adapter):
    """Dynamically creates the key=value arguments for the `mk` command
    based upon the type being created.
    """
    implements(IContextualCmdArgumentsSyntax)

    context(CreateObjCmd)

    def arguments(self, parser, args, rest):
        model_cls = creatable_models.get(args.type)
        schemas = get_direct_interfaces(model_cls)

        parser.declare_argument('keywords', {})

        for schema in schemas:
            for name, field in zope.schema.getFields(schema).items():

                choices = ([i.value.encode('utf-8') for i in field.vocabulary]
                           if isinstance(field, zope.schema.Choice) else
                           None)

                type = (int if isinstance(field, zope.schema.Int)
                        else None)

                parser.add_argument('=' + name, required=True, type=type, action=GroupDictAction,
                                    group='keywords', help=field.title.encode('utf8'), choices=choices)

        return parser


class HelpCmd(Cmd):
    """Outputs the names of all commands."""
    implements(ICmdArgumentsSyntax)

    command('help')

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        choices = [name for name in registry.commands().keys() if name]
        parser.add_argument('command', nargs='?', choices=choices, help="command to get help for")
        return parser

    @defer.inlineCallbacks
    def execute(self, args):
        if args.command:
            yield registry.get_command(args.command)(self.protocol).parse_args(['-h'])
        commands = [command._format_names() for command in set(registry.commands().values()) if command.name]
        self.write("valid commands: %s\n" % (', '.join(sorted(commands))))


class QuitCmd(Cmd):
    """Quits the console."""

    command('quit')

    def execute(self, args):
        self.protocol.close_connection()


class LastErrorCmd(Cmd):
    """Prints out the last error.

    Useful for devs, and users reporting to issue tracker.
    (Inspired by xsbt)

    """

    command('last_error')

    def execute(self, args):
        if self.protocol.last_error:
            cmdline, failure = self.protocol.last_error
            self.write("Error executing '%s': %s" % (cmdline, failure))
