import os, inspect

import transaction
import zope.schema
import time
import datetime
from collections import OrderedDict
from grokcore.component import implements, context, Adapter, Subscription, baseclass, order
from twisted.conch.insults.insults import modes
from twisted.internet import defer
from zope.component import provideSubscriptionAdapter, provideAdapter
from zope.interface import directlyProvidedBy

from opennode.oms.endpoint.ssh.cmd import registry
from opennode.oms.endpoint.ssh.cmd.base import Cmd
from opennode.oms.endpoint.ssh.cmd.directives import command, alias
from opennode.oms.endpoint.ssh.cmdline import ICmdArgumentsSyntax, IContextualCmdArgumentsSyntax, GroupDictAction, VirtualConsoleArgumentParser
from opennode.oms.endpoint.ssh.colored_columnize import columnize

import opennode.oms.model.schema
from opennode.oms.endpoint.ssh.terminal import BLUE, CYAN, GREEN
from opennode.oms.model.form import ApplyRawData
from opennode.oms.model.traversal import canonical_path
from opennode.oms.model.model import creatable_models
from opennode.oms.model.model.base import IContainer, IIncomplete
from opennode.oms.model.model.bin import ICommand
from opennode.oms.model.model.proc import Proc
from opennode.oms.model.model.symlink import Symlink, follow_symlinks
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
        parser.add_argument('-P', action='store_true', help="use physical directory structure instead of following symbolic links")
        return parser

    @db.transact
    def execute(self, args):
        if not args.path:
            self.path = [self.path[0]]
            self.obj_path = [self.obj_path[0]]
            return

        # Cleanup '..'s from path using the logical path.
        # Only handles trailing '..'s for now.
        if not args.P:
            import itertools
            ups = len(list(itertools.takewhile(lambda i: i=='..', args.path.split('/'))))
            ups = min(ups, len(self.path) - 1)
            if ups:
                self.path = self.path[0:-ups]
                self.obj_path = self.obj_path[0:-ups]
                args.path = args.path[ups*len('../'):]

        # Delegate path traversal to physical traversal.
        # It's possible that we emptied the path by removing all '..'s.
        if args.path:
            self._do_traverse(args.path)

        # Recompute new absolute path if physical path was requested.
        if args.P:
            current = self.current_obj
            self.path = []
            self.obj_path = []
            while current:
                self.path.insert(0, current.__name__)
                self.obj_path.insert(0, db.ref(current))
                current = current.__parent__

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

        # Fixes #41.
        if os.path.isabs(path):
            objs.insert(0, db.deref(self.obj_path[0]))


        # Handle '//foo/bar//fee'
        path_components = path.split('/')
        path_components[1:] = [i for i in path_components[1:] if i != '']

        for obj, name in zip(objs, path_components):
            ref = db.ref(obj)
            try:
                # Try to find the object in the current path:
                overlap = self.obj_path.index(ref)
            except ValueError:
                # ... if not found, add it:
                self.obj_path.append(ref)
                self.path.append(name)
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
            elif ICommand.providedBy(item):
                return self.protocol.colorize(GREEN, item.__name__ + '*')
            elif isinstance(item, Symlink):
                return self.protocol.colorize(CYAN, item.__name__ + '@')
            else:
                return item.__name__

        def sorted_obj_list():
            return sorted(obj.listcontent(), key=lambda o: o.__name__)

        if self.opts_long:
            def nick(item):
                if isinstance(item, Symlink):
                    return [canonical_path(item)] + getattr(follow_symlinks(item), 'nicknames', [])
                return getattr(item, 'nicknames', [])

            if IContainer.providedBy(obj):
                for subobj in sorted_obj_list():
                    self.write(('%s\t%s\n' % (pretty_name(subobj), ' : '.join(nick(subobj)))).encode('utf8'))
            else:
                self.write(('%s\t%s\n' % (pretty_name(obj), ' : '.join(nick(obj)))).encode('utf8'))
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
        if len(schemas) == 0:
            self.write("Unable to create a printable representation.\n")
            return

        for schema in schemas:
            fields = zope.schema.getFieldsInOrder(schema)
            data = OrderedDict()
            for name, field in fields:
                key = field.description or field.title
                key = key.encode('utf8')
                data[key] = field.get(obj)

            if data:
                max_key_len = max(len(key) for key in data)
                for key, value in data.items():
                    self.write("%s\t%s\n" % ((key + ':').ljust(max_key_len),
                                             str(value).encode('utf8')))

        if IIncomplete.providedBy(obj):
            self.write("-----------------\n")
            self.write("This %s is incomplete.\n" % (type(obj).__name__))


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

        rename = None

        # move and rename
        if not dest:
            dest = self.traverse(os.path.dirname(dest_path))
            rename = os.path.basename(dest_path)

        if not IContainer.providedBy(dest):
            self.write("Destination %s has to be a container.\n" % dest)
            return

        # `add` will take care of removing the old parent.
        dest.add(src)
        if rename:
            dest.rename(src.__name__, rename)

        transaction.commit()


class SetAttrCmd(Cmd):
    implements(ICmdArgumentsSyntax)

    command('set')

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('path')
        return parser

    @db.transact
    def execute(self, args):
        obj = self.traverse(args.path)
        if not obj:
            self.write("No such object: %s\n" % args.path)
            return

        raw_data = args.keywords

        if args.verbose:
            for key, value in raw_data.items():
                self.write("Setting %s=%s\n" % (key, value))

        form = ApplyRawData(raw_data, obj)

        if not form.errors:
            form.apply()
        else:
            form.write_errors(to=self)

        transaction.commit()


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
            form.write_errors(to=self)


class SetOrMkCmdDynamicArguments(Adapter):
    """Dynamically creates the key=value arguments for the `set` and `mk` commands
    depending on the object or type being edited or created.

    """
    implements(IContextualCmdArgumentsSyntax)
    baseclass()

    @db.transact
    def arguments(self, parser, args, rest):
        parser.declare_argument('keywords', {})

        model_or_obj, args_required = ((creatable_models.get(args.type), True)
                                       if self.context.name == 'mk' else
                                       (self.context.traverse(args.path), False))

        schemas = get_direct_interfaces(model_or_obj)

        for schema in schemas:
            for name, field in zope.schema.getFields(schema).items():
                if field.readonly:
                    continue

                choices = ([i.value.encode('utf-8') for i in field.vocabulary]
                           if isinstance(field, zope.schema.Choice) else
                           None)

                type = (int if isinstance(field, zope.schema.Int)
                        else None)

                kwargs = {}
                if isinstance(field, opennode.oms.model.schema.Path):
                    kwargs['is_path'] = True
                    kwargs['base_path'] = field.base_path

                parser.add_argument('=' + name, required=args_required and field.required, type=type, action=GroupDictAction,
                                    group='keywords', help=field.title.encode('utf8'), choices=choices, **kwargs)

        return parser


provideAdapter(SetOrMkCmdDynamicArguments, adapts=(SetAttrCmd, ))
provideAdapter(SetOrMkCmdDynamicArguments, adapts=(CreateObjCmd, ))


class FileCmd(Cmd):
    """Outputs the type of an object."""
    implements(ICmdArgumentsSyntax)

    command('file')
    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('paths', nargs='+')
        return parser

    @db.transact
    def execute(self, args):
        rows = []

        for path in args.paths:
            obj = self.traverse(path)
            if not obj:
                self.write("No such object: %s\n" % path)
            else:
                rows.append(self._do_file(path, obj))

        width = max(len(i[0]) for i in rows)
        for row in rows:
            self.write("%s %s" % (row[0].ljust(width), row[1]))

    def _do_file(self, path, obj):
        ifaces = ', '.join([i.__name__ for i in obj.implemented_interfaces()])
        return (path+":", "%s%s %s\n" % (type(obj).__name__, ':' if ifaces else '', ifaces))


class EchoCmd(Cmd):
    """Outputs the command line arguments."""
    implements(ICmdArgumentsSyntax)

    command('echo')

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('strings', nargs='*')
        return parser

    def execute(self, args):
        self.write("%s\n" % (" ".join(args.strings)))


class HelpCmd(Cmd):
    """Outputs the names of all commands."""
    implements(ICmdArgumentsSyntax)

    command('help')

    @defer.inlineCallbacks
    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        choices = [i.name for i in (yield self._commands())]
        parser.add_argument('command', nargs='?', choices=choices, help="command to get help for")
        defer.returnValue(parser)

    @defer.inlineCallbacks
    def execute(self, args):
        if args.command:
            yield self._cmd_help(args.command)
        else:
            self.write("valid commands: %s\n" % (', '.join(sorted(i._format_names() for i in (yield self._commands())))))

    @db.transact
    def _cmd_help(self, name):
        # for some reason I wasn't able to use inlineCallbacks here
        # the ArgumentParsing exception is normal and expected
        deferred = self.protocol.get_command_class(name)(self.protocol).parse_args(['-h'])
        @deferred
        def on_error(*args):
            pass

    @db.transact
    def _commands(self):
        dummy = NoCommand(self.protocol)

        cmds = []
        for d in self.protocol.environment['PATH'].split(':'):
            for i in dummy.traverse(d) or []:
                if ICommand.providedBy(i):
                    cmds.append(i.cmd)
        return cmds

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


class HistoryCmd(Cmd):
    """Prints the shell history."""

    command('history')

    def execute(self, args):
        for i in self.protocol.historyLines:
            self.write("%s\n" % i)


class PrintEnvCmd(Cmd):
    """Prints the environment variables."""

    command('printenv')

    def execute(self, args):
        for name, value in self.protocol.environment.items():
            self.write("%s=%s\n" % (name, value))


class SetEnvCmd(Cmd):
    """Modifies the environment variables."""
    implements(ICmdArgumentsSyntax)

    command('setenv')

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('name')
        parser.add_argument('value')
        return parser

    def execute(self, args):
        self.protocol.environment[args.name] = args.value


class SleepCmd(Cmd):
    """Do nothing for some time."""
    implements(ICmdArgumentsSyntax)

    command('sleep')

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('seconds')
        return parser

    # actually not db, but requires a thread
    @db.transact
    def execute(self, args):
        time.sleep(float(args.seconds))


class TaskListCmd(Cmd):
    """Emulates 'ps' command, including bsd args."""

    command('ps')

    implements(ICmdArgumentsSyntax)

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('bsd', nargs='*', help="Ignored bsd args, for those who have unix type habits (e.g. 'ps xa')")
        parser.add_argument('-d', action='store_true', help="Show recently finished (dead) tasks.")
        parser.add_argument('-l', action='store_true', help="Show parent task id")
        return parser

    @db.transact
    def execute(self, args):
        # ignore arguments
        tasks = Proc().tasks
        if args.d:
            tasks = Proc().dead_tasks

        max_key_len = max(3, *[len(i) for i in Proc().content().keys()])

        self.write("%s    %sTIME CMD\n" % ("TID".rjust(max_key_len), "PTID    ".rjust(max_key_len) if args.l else ''))
        for tid, task in tasks.items():
            ptid = task.ptid
            self.write("%s %s%s %s\n" % (tid.rjust(max_key_len), (ptid + ' ').rjust(max_key_len) if args.l else '', datetime.timedelta(0, int(task.uptime)), task.cmdline))


class OmsShellCmd(Cmd):
    """This command represents the oms shell. Currently it cannot run a nested shell."""

    command('omsh')

    def execute(self, args):
        self.write("nested shell not implemented yet.\n")


class TerminalResetCmd(Cmd):
    """Resets terminal. Useful after interrupting an attach."""
    implements(ICmdArgumentsSyntax)

    command("reset")

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('-p', action='store_true', help="Reset private modes")
        return parser

    def execute(self, args):
        if args.p:
            self.protocol.terminal.resetPrivateModes('1')
            return
        self.protocol.terminal.reset()
        self.terminal.setModes((modes.IRM, ))
