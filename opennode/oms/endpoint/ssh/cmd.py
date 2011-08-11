import transaction
from columnize import columnize
from twisted.internet import defer, reactor
from twisted.python.failure import Failure
from twisted.python.threadable import isInIOThread
import zope.schema

from opennode.oms.zodb import db
from opennode.oms.model.form import apply_raw_data
from opennode.oms.model.traversal import traverse_path
from opennode.oms.model.model.base import IContainer
from opennode.oms.util import get_direct_interfaces


class Cmd(object):

    def __init__(self, protocol):
        self.protocol = protocol
        self.terminal = protocol.terminal

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



class cmd_cd(Cmd):

    def __call__(self, *args):
        if len(args) > 1:
            raise Exception('cd takes at most 1 argument')

        if not args:
            self.protocol.path = [self.path[0]]
            self.protocol.obj_path = [self.obj_path[0]]
            return

        path = args[0]
        deferred = self._do_traverse(path)

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

    @db.transact
    def __call__(self, *args):
        args = list(args)

        self.opts_long = ('-l' in args)
        if self.opts_long:
            args.pop(args.index('-l'))

        if args:
            for path in args:
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


class cmd_pwd(Cmd):
    def __call__(self, *args):
        self.write('%s\n' % self.protocol._cwd())


class cmd_cat(Cmd):

    @db.transact
    def __call__(self, *args):
        for path in args:
            obj = self.traverse(path)
            if not obj:
                self.write('No such object: %s\n' % path)
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

    def _usage(self):
        self.write("Usage: set obj key=value [key=value ..]\n\n"
                   "Sets attributes on objects.\n"
                   "If setting or parsing of one of the attributes fails, "
                   "the operation is cancelled and the object unchanged.\n")

class cmd_help(Cmd):
    """Get the names of the commands from this modules and prints them out."""
    def __call__(self, *args):
        self.write('valid commands: %s\n' % (", ".join(commands().keys())))

def commands():
    """Create a map of command names to command objects."""
    return {name[4:]: cmd for name, cmd in globals().iteritems() if name.startswith('cmd_')}
