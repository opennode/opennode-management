from columnize import columnize
from twisted.internet import defer, reactor
from twisted.python.failure import Failure
from twisted.python.threadable import isInIOThread

from opennode.oms.zodb import db
from opennode.oms.model.traversal import traverse_path
from opennode.oms.model.model import IContainer


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
                    self._do_ls(obj)
        else:
            self._do_ls(self.current_obj)

    def _do_ls(self, obj):
        if self.opts_long:
            for item in obj.listcontent():
                self.write(('%s\t%s\n' % (item.name, ':'.join(item.nicknames))).encode('utf8'))
        else:
            items = list(obj.listnames())
            if items:
                output = columnize(items, displaywidth=self.protocol.width)
                self.write(output)


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
        data = obj.to_dict()
        if data:
            max_key_len = max(len(key) for key in data)
            for key, value in sorted(data.items()):
                self.write('%s\t%s\n' % ((key + ':').ljust(max_key_len),
                                         str(value).encode('utf8')))
