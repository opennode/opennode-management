from twisted.internet import defer
from columnize import columnize

from opennode.oms import db
from opennode.oms.model.traversal import traverse_path


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

    def cmd(self, cmd_name):
        cmd_cls_name = ('cmd_%s' % cmd_name)
        assert cmd_cls_name in globals()
        cmd_cls = globals()[cmd_cls_name]
        return cmd_cls(self.protocol)


class cmd_cd(Cmd):

    def __call__(self, *args):
        if len(args) > 1:
            raise Exception('cd takes at most 1 argument')

        if not args:
            self.path = [self.path[0]]
            self.obj_path = [self.obj_path[0]]
            return

        path = args[0]
        deferred = self._do_traverse(path)

        @deferred
        def on_error(f):
            self.terminal.write(str(f))

        d = defer.Deferred()
        deferred.addBoth(lambda *args: d.callback(None))
        return d

    @db.transact
    def _do_traverse(self, path):
        objs, unresolved_path = traverse_path(db.deref(self.current_obj), path)

        if not objs or unresolved_path:
            self.terminal.write('No such object: %s' % path)
            self.terminal.nextLine()
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
                self.terminal.write(item.name + '\t' + ':'.join(item.nicknames).encode('utf8'))
                self.terminal.nextLine()
        else:
            items = list(obj.listnames())
            if items:
                output = columnize(items, displaywidth=self.protocol.width)
                self.terminal.write(output)


class cmd_pwd(Cmd):
    def __call__(self, *args):
        self.terminal.write(self.protocol._cwd())
        self.terminal.nextLine()


class cmd_cat(Cmd):
    @db.transact
    def __call__(self, *args):
        if not args:
            obj = self.current_obj
            obj = db.deref(obj)
            objs = [obj]
        else:
            objs = []
            for name in args:
                obj = self.cmd('cd').traverse(name)
                objs.append(obj)

        for obj in objs:
            if obj:
                self._do_cat(obj)
            else:
                self.terminal.write('No such object: %s\n' % name)

    def _do_cat(self, obj):
        data = obj.to_dict()
        if data:
            max_key_len = max(len(key) for key in data)
            for key, value in sorted(data.items()):
                self.terminal.write('%s\t%s\n' % ((key + ':').ljust(max_key_len),
                                                  str(value).encode('utf8')))
