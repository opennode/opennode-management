from columnize import columnize
from twisted.internet import defer

from opennode.oms.db import db
from opennode.oms.model.traversal import traverse_path
from opennode.oms.model.model import Root


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
        return self.obj_path[-1]

    def write(self, *args):
        self.terminal.write(*args)

    def traverse(self, path):
        if path.startswith('/'):
            return traverse_path(Root(), path[1:])
        else:
            return traverse_path(db.deref(self.current_obj), path)


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
        objs, unresolved_path = traverse_path(db.deref(self.current_obj), path)

        if not objs or unresolved_path:
            self.write('No such object: %s\n' % path)
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
                self.path.append(obj.name)
            else:
                # ... otherwise remove everything that follows it:
                self.obj_path[overlap+1:] = []
                self.path[overlap+1:] = []


class cmd_ls(Cmd):

    @db.transact
    def __call__(self, *args):
        obj = db.deref(self.obj_path[-1])

        if '-l' in args:
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
        for name in args:
            objs, unresolved_path = traverse_path(db.deref(self.current_obj), name)
            if not objs or unresolved_path:
                self.write('No such object: %s\n' % name)
            else:
                self._do_cat(objs[-1])

    def _do_cat(self, obj):
        data = obj.to_dict()
        if data:
            max_key_len = max(len(key) for key in data)
            for key, value in sorted(data.items()):
                self.write('%s\t%s\n' % ((key + ':').ljust(max_key_len),
                                         str(value).encode('utf8')))
