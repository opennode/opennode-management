import datetime
import os
import re
import time

import transaction
import zope.schema
from grokcore.component import implements, Adapter, Subscription, baseclass, order
from twisted.conch.insults.insults import modes
from twisted.internet import defer, utils
from twisted.python import log
from zope.authentication.interfaces import IAuthentication
from zope.component import getUtility
from zope.component import provideSubscriptionAdapter, provideAdapter, handle
from zope.security.proxy import removeSecurityProxy

from opennode.oms.endpoint.ssh.editor import Editor
from opennode.oms.endpoint.ssh.editable import IEditable
from opennode.oms.endpoint.ssh.cmd.base import Cmd
from opennode.oms.endpoint.ssh.cmd.security import pretty_effective_perms
from opennode.oms.endpoint.ssh.cmd.directives import command, alias
from opennode.oms.endpoint.ssh.cmdline import (ICmdArgumentsSyntax, IContextualCmdArgumentsSyntax,
                                               GroupDictAction, VirtualConsoleArgumentParser)
from opennode.oms.endpoint.ssh.colored_columnize import columnize
from opennode.oms.endpoint.ssh.terminal import BLUE, CYAN, GREEN
from opennode.oms.model.form import RawDataApplier, RawDataValidatingFactory, ModelDeletedEvent
from opennode.oms.model.model import creatable_models
from opennode.oms.model.model.base import IContainer, IIncomplete
from opennode.oms.model.model.bin import ICommand
from opennode.oms.model.model.proc import Proc
from opennode.oms.model.model.symlink import Symlink, follow_symlinks
from opennode.oms.model.schema import Path, get_schema_fields, model_to_dict
from opennode.oms.model.traversal import canonical_path
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
        parser.add_argument('-v', '--verbose', action='count',
                            help="be verbose, use it multiple times to increase verbosity")
        return parser


class ChangeDirCmd(Cmd):
    implements(ICmdArgumentsSyntax)

    command('cd')

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('path', nargs='?')
        parser.add_argument('-P', action='store_true',
                            help="use physical directory structure instead of following symbolic links")
        return parser

    @db.ro_transact
    def execute(self, args):
        if not args.path:
            self.path = [self.path[0]]
            self.obj_path = [self.obj_path[0]]
            return

        # Cleanup '..'s from path using the logical path.
        # Only handles trailing '..'s for now.
        self._resolve_up_dir(args)

        # Delegate path traversal to physical traversal.
        # It's possible that we emptied the path by removing all '..'s.
        self._resolve_path(args)

        # Recompute new absolute path if physical path was requested.
        self._resolve_physical_path(args)

    @db.ro_transact(proxy=False)
    def subject(self, args):
        return tuple((self.current_obj, self.traverse(args.path if args.path else self.path[0])))

    def _resolve_physical_path(self, args):
        # Recompute new absolute path if physical path was requested.
        if args.P:
            current = self.current_obj
            self.path = []
            self.obj_path = []
            while current:
                self.path.insert(0, current.__name__)
                self.obj_path.insert(0, db.ref(current))
                current = current.__parent__

    def _resolve_path(self, args):
        # Delegate path traversal to physical traversal.
        # It's possible that we emptied the path by removing all '..'s.
        if args.path:
            if args.path == '-':
                if self.protocol.path_stack:
                    args.path = self.protocol.path_stack.pop()
            self.protocol.path_stack.insert(0, self.protocol._cwd())
            self._do_traverse(args.path)

    def _resolve_up_dir(self, args):
        # Cleanup '..'s from path using the logical path.
        # Only handles trailing '..'s for now.
        if not args.P:
            import itertools
            ups = len(list(itertools.takewhile(lambda i: i == '..', args.path.split('/'))))
            ups = min(ups, len(self.path) - 1)
            if ups:
                self.path = self.path[0:-ups]
                self.obj_path = self.obj_path[0:-ups]
                args.path = args.path[ups * len('../'):]

    def _do_traverse(self, path):
        objs, unresolved_path = self.traverse_full(path)

        if not objs or unresolved_path:
            self.write('No such object: %s\n' % path)
            return

        if not IContainer.providedBy(objs[-1]):
            self.write('Cannot cd to a non-container\n')
            return

        # Fixes #41.
        if os.path.isabs(path):
            objs.insert(0, db.deref(self.obj_path[0]))

        # Handle '//foo/bar//fee'
        path_components = path.split('/')
        path_components[1:] = [comp for comp in path_components[1:] if comp != '']

        oms_root = self.obj_path[0]

        if path_components[0] == '':
            del self.obj_path[:]
            del self.path[:]

        for obj, name in zip(objs, path_components):
            ref = db.ref(obj)
            if name == '.' or (ref == oms_root and oms_root in self.obj_path):
                continue
            self.obj_path.append(ref)
            self.path.append(name)


class ListDirContentsCmd(Cmd):
    implements(ICmdArgumentsSyntax)

    command('ls')

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('-l', action='store_true', help="long")
        parser.add_argument('-R', action='store_true', help="recursive")
        parser.add_argument('-d', action='store_true',
                            help="list directory entries instead of contents, and do not dereference "
                            "symbolic links")
        parser.add_argument('paths', nargs='*')
        return parser

    @db.ro_transact
    def execute(self, args):
        self.opts_long = args.l
        self.opts_dir = args.d
        self.visited = []

        if args.paths:
            for path in args.paths:
                obj = self.traverse(path)
                if not obj:
                    self.write('No such object: %s\n' % path)
                else:
                    self._do_ls(obj, path, recursive=args.R)
        else:
            self._do_ls(self.current_obj, recursive=args.R)

    @db.ro_transact(proxy=False)
    def subject(self, args):
        if args.paths:
            return tuple(self.traverse(path) for path in args.paths)
        else:
            return tuple((self.current_obj,))

    def _do_ls(self, obj, path='.', recursive=False):
        assert obj not in self.visited
        self.visited.append(obj)

        def pretty_name(item):
            if IContainer.providedBy(item):
                return self.protocol.colorize(BLUE, '%s/' % (item.__name__,))
            elif ICommand.providedBy(item):
                return self.protocol.colorize(GREEN, '%s*' % (item.__name__,))
            elif isinstance(item, Symlink):
                return self.protocol.colorize(CYAN, '%s@' % (item.__name__,))
            else:
                return item.__name__

        def make_long_lines(container):
            def nick(item):
                if isinstance(item, Symlink):
                    return [canonical_path(item)] + getattr(follow_symlinks(item), 'nicknames', [])
                return getattr(item, 'nicknames', [])

            def owner(item):
                return item.__owner__ or 'root'

            return [(('%s %s\t%s\t%s\n' % (pretty_effective_perms(self.protocol.interaction,
                                                                  follow_symlinks(subobj)),
                                           owner(subobj),
                                           pretty_name(subobj),
                                           ' : '.join(nick(subobj)))).encode('utf8'))
                    for subobj in container]

        def make_short_lines(container):
            return columnize([pretty_name(subobj) for subobj in container], displaywidth=self.protocol.width)

        container = (sorted(filter(lambda i: self.protocol.interaction.checkPermission('view', i),
                                   obj.listcontent()),
                            key=lambda o: o.__name__)
                     if IContainer.providedBy(obj) and not self.opts_dir
                     else [obj])

        for line in (make_long_lines(container) if self.opts_long else make_short_lines(container)):
            self.write(line)

        if recursive and IContainer.providedBy(obj) and not self.opts_dir:
            for ch in container:
                child_obj = obj[ch.__name__]
                if (IContainer.providedBy(child_obj)
                        and not isinstance(child_obj, Symlink)
                        and child_obj not in self.visited):
                    self.write("\n%s:\n" % os.path.join(path, ch.__name__.encode('utf8')))
                    self._do_ls(child_obj, os.path.join(path, ch.__name__), recursive=True)


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
        parser.add_argument('-o', action='append')
        parser.add_argument('-H', action='store_true')
        return parser

    @db.ro_transact(proxy=False)
    def subject(self, args):
        return tuple(self.traverse(path) for path in args.paths)

    @db.transact
    def execute(self, args):
        attrs = []
        for i in args.o or []:
            for attr in i.split(','):
                attrs.append(attr.strip())

        for path in args.paths:
            obj = self.traverse(path)
            if not obj:
                self.write("No such object: %s\n" % path)
            else:
                self._do_cat(obj, attrs, path if args.H else None)

    def _do_cat(self, obj, attrs, filename=None):
        name = '%s: ' % filename if filename else ''

        data = [(key, value, name + title)
                for (key, value), title
                in zip(model_to_dict(obj).items(), model_to_dict(obj, use_titles=True).keys())
                if key in attrs or not attrs]

        if data:
            max_title_len = max(len(title) for key, _, title in data)
            for key, value, title in data:
                if isinstance(value, dict):
                    # security proxies don't mimic tuple() perfectly
                    # thus cannot be passed to "%" directly
                    pretty_value = ', '.join(['%s:%s' % tuple(i) for i in value.items()])
                elif hasattr(value, '__iter__'):
                    strings = [str(i) for i in value]
                    if not isinstance(value, tuple):
                        strings = sorted(strings)
                    pretty_value = ', '.join(strings)
                else:
                    pretty_value = value
                self.write("%s\t%s\n" % ((title.encode('utf8') + ':').ljust(max_title_len),
                                         str(pretty_value).encode('utf8')))

        if not attrs and IIncomplete.providedBy(obj):
            self.write("-----------------\n")
            self.write("This %s is incomplete.\n" % (type(removeSecurityProxy(obj)).__name__))


class RemoveCmd(Cmd):
    """Deletes an object."""
    implements(ICmdArgumentsSyntax)

    command('rm')

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('paths', nargs='+')
        parser.add_argument('-f', action='store_true')
        return parser

    @db.transact
    def execute(self, args):
        for path in args.paths:
            obj_dir = self.current_obj

            # cleanup trailing slash
            if path.endswith('/'):
                path = path[:-1]

            if os.path.dirname(path):
                obj_dir = self.traverse(os.path.dirname(path))

            obj = obj_dir[os.path.basename(path)]

            if not obj_dir or not obj:
                self.write("No such object: %s\n" % path)
                continue

            parent = obj.__parent__
            del obj_dir[obj.__name__]

            try:
                handle(obj, ModelDeletedEvent(parent))
            except Exception:
                if not args.f:
                    raise

    @db.ro_transact(proxy=False)
    def subject(self, args):
        def get_subjects():
            for path in args.paths:
                obj_dir = self.current_obj

                if path.endswith('/'):
                    path = path[:-1]

                if os.path.dirname(path):
                    obj_dir = self.traverse(os.path.dirname(path))

                yield obj_dir[os.path.basename(path)]
        return tuple(obj for obj in get_subjects())


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

    @db.ro_transact(proxy=False)
    def subject(self, args):
        return tuple(self.traverse(path) for path in args.paths)


class SetAttrCmd(Cmd):
    implements(ICmdArgumentsSyntax)

    command('set')

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('path')
        return parser

    @db.ro_transact(proxy=False)
    def subject(self, args):
        return tuple((self.traverse(args.path),))

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

        form = RawDataApplier(raw_data, obj)

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

    @db.ro_transact(proxy=False)
    def subject(self, args):
        return tuple((self.current_obj, ))

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

        form = RawDataValidatingFactory(args.keywords, model_cls,
                                        marker=getattr(self.current_obj, '__contains__', None))

        if not form.errors:
            obj = form.create()
            obj_id = self.current_obj.add(obj)

            interaction = self.protocol.interaction
            if not interaction:
                auth = getUtility(IAuthentication, context=None)
                principal = auth.getPrincipal(None)
            else:
                principal = interaction.participations[0].principal

            obj.__owner__ = principal

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

        schema_fields = get_schema_fields(model_or_obj,
                                          marker=getattr(self.context.current_obj, '__contains__', None))

        for name, field, schema in schema_fields:
            if field.readonly:
                continue

            field = field.bind(model_or_obj)

            choices = ([i.value.encode('utf-8') for i in field.vocabulary]
                       if isinstance(field, zope.schema.Choice) else None)

            type = (int if isinstance(field, zope.schema.Int) else None)

            kwargs = {}
            if isinstance(field, Path):
                kwargs['is_path'] = True

                base_path = '.'
                if field.relative_to == Path.PARENT:
                    if self.context.name == 'mk':
                        base_path = self.context.protocol._cwd()
                    else:
                        base_path = canonical_path(model_or_obj.__parent__)

                kwargs['base_path'] = os.path.join(base_path, field.base_path)

            parser.add_argument('=%s' % name, required=(args_required and field.required),
                                type=type, action=GroupDictAction, group='keywords',
                                help=field.title.encode('utf8'), choices=choices, **kwargs)

        return parser


provideAdapter(SetOrMkCmdDynamicArguments, adapts=(SetAttrCmd, ))
provideAdapter(SetOrMkCmdDynamicArguments, adapts=(CreateObjCmd, ))


class LinkCmd(Cmd):
    """Creates a (sym)link to an object."""
    implements(ICmdArgumentsSyntax)

    command('ln')

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('-s', action='store_true', help="ignored, as we only have symbolic links")
        parser.add_argument('-f', action='store_true', help="Force, delete destination if exists")
        parser.add_argument('src')
        parser.add_argument('dst')
        return parser

    @db.transact
    def execute(self, args):
        src_obj = self.traverse(args.src)
        if not src_obj:
            self.write("cannot create symlink: Source file not found\n")
            return

        dst_obj = self.traverse(args.dst)
        if dst_obj:
            if args.f:
                self.write("currently -f is not implemented\n")
                # del dst_obj.__parent__[dst_obj.__name__]
            else:
                self.write("cannot create symlink: File exists\n")
                return

        dst_dir = self.current_obj
        if os.path.dirname(args.dst):
            dst_dir = self.traverse(os.path.dirname(args.dst))

        dst_dir.add(Symlink(os.path.basename(args.dst), src_obj))

    @db.ro_transact(proxy=False)
    def subject(self, args):
        return tuple((self.traverse(args.src), self.traverse(args.dst)))


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

        if not rows:
            return

        width = max(len(i[0]) for i in rows)
        for row in rows:
            self.write("%s %s" % (row[0].ljust(width), row[1]))

    def _do_file(self, path, obj):
        ifaces = ', '.join(obj.get_features())
        return (path + ":", "%s%s %s\n" % (type(removeSecurityProxy(obj)).__name__, ':' if ifaces else '', ifaces))

    @db.ro_transact(proxy=False)
    def subject(self, args):
        return tuple(self.traverse(path) for path in args.paths)


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
            cmd_names = ', '.join(sorted(i._format_names() for i in (yield self._commands())))
            self.write("valid commands: %s\n" % cmd_names)

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
            self.write("Error executing '%s': %s\n" % (cmdline, failure))
            import traceback
            self.write("error type %s\n" % (type(failure)))
            self.write(''.join(traceback.format_exception(*failure)))


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
        parser.add_argument('bsd', nargs='*',
                            help="Ignored bsd args, for those who have unix type habits (e.g. 'ps xa')")
        parser.add_argument('-d', action='store_true',
                            help="Show recently finished (dead) tasks.")
        parser.add_argument('-l', action='store_true',
                            help="Show parent task id")
        return parser

    @db.ro_transact
    def execute(self, args):
        # ignore arguments
        tasks = Proc().tasks
        if args.d:
            tasks = Proc().dead_tasks

        max_key_len = max(3, *[len(i) for i in Proc().content().keys()])
        max_user_len = max(3, *[len(i.principal.id) for i in Proc().content().values() if getattr(i, 'principal', None)])

        self.write("%s    %s%s TIME CMD\n" % ("TID".rjust(max_key_len),
                                           "PTID    ".rjust(max_key_len) if args.l else '',
                                           "USER   ".ljust(max_user_len)))

        for tid, task in tasks.items():
            ptid = task.ptid
            self.write("%s %s   %s %s %s\n" %
                       (tid.rjust(max_key_len),
                        (ptid + ' ').rjust(max_key_len) if args.l else '',
                        (task.principal.id if task.principal else '-').ljust(max_user_len),
                        datetime.timedelta(0, int(task.uptime)),
                        task.cmdline))


class KillTaskCmd(Cmd):
    """Implement the kill command which can send signals to tasks."""

    command('kill')

    implements(ICmdArgumentsSyntax)

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('tid', nargs='*',
                            help="Task id")
        parser.add_argument('-STOP', action='store_true',
                            help="Pauses the task")
        parser.add_argument('-CONT', action='store_true',
                            help="Unpauses the task")
        return parser

    def execute(self, args):
        for tid in args.tid:
            task = self.find_task(tid)
            if not task:
                self.write("Cannot find task `%s`\n" % tid)
                continue

            if args.STOP:
                action = "STOP"
            elif args.CONT:
                action = "CONT"
            else:
                action = "TERM"

            task.signal(action)

    def find_task(self, tid):
        tasks = Proc().tasks

        if re.match('[0-9]+$', tid):
            return tasks[tid]
        else:
            candidates = []
            for i in tasks.values():
                if tid in str(i.cmdline):
                    candidates.append(i)
            if len(candidates) == 1:
                return candidates[0]

        return None


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


class EditCmd(Cmd):
    implements(ICmdArgumentsSyntax)

    command("edit")

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('path')
        parser.add_argument('-n', action='store_true', help="No descriptions")
        return parser

    @defer.inlineCallbacks
    def execute(self, args):
        obj = yield db.ro_transact(self.traverse)(args.path)
        if not obj:
            self.write("No such object: %s\n" % args.path)
            return

        editor = Editor(self.protocol)

        old = IEditable(obj).toEditableString(descriptions=not args.n)
        updated = yield editor.start(old)

        yield self._save(args, old, updated)

    @db.ro_transact(proxy=False)
    def subject(self, args):
        return tuple((self.traverse(args.path),))

    @db.transact
    def _save(self, args, old, updated):
        obj = self.traverse(args.path)

        if old == updated:
            self.write("No changes\n")
        else:
            raw_data = {}
            for line in updated.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    raw_data[key.strip()] = value.strip()
            form = RawDataApplier(raw_data, obj)
            if not form.errors:
                form.apply()
            else:
                form.write_errors(to=self)

            transaction.commit()


class CatLogCmd(Cmd):
    implements(ICmdArgumentsSyntax)
    command('catlog')

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('-n', help='Number of lines to output')
        parser.add_argument('-u', action='store_true', required=False, default=False,
                            help='Display just user log')
        return parser

    @defer.inlineCallbacks
    def execute(self, args):
        from opennode.oms.config import get_config
        logfilename = get_config().get('logging', 'file')

        if logfilename == 'stdout':
            log.msg('System is configured to log to stdout. Cannot cat to omsh terminal',
                    system='catlog')
            defer.returnValue(None)

        nr_of_lines = int(args.n) if args.n is not None else 10

        outputCb = utils.getProcessOutput("tail",
                                          args=('-n %s' % nr_of_lines, logfilename),
                                          errortoo=True)
        outputCb.addCallback(lambda output: self.write(output))
        yield outputCb
