from twisted.internet import defer
from columnize import columnize

from opennode.oms import db
from opennode.oms.model.traversal import ITraverser


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

    @defer.inlineCallbacks
    def __call__(self, *args):
        if len(args) > 1:
            raise Exception('cd takes at most 1 argument')
        else:
            path = args[0].split('/') if args else []

        for name in path:
            success = yield defer.maybeDeferred(self._do_cmd, name)
            if not success:
                self.terminal.write('No such file or directory: %s' % name)
                self.terminal.nextLine()
                break

    def _do_cmd(self, name):
        if not name:
            self.path = [self.path[0]]
            self.obj_path = [self.obj_path[0]]
        elif name == '..':
            if len(self.path) > 1:
                self.path.pop()
                self.obj_path.pop()
        elif name == '.':
            pass
        else:
            return self._traverse(name)
        return True

    @db.transact
    def _traverse(self, name):
        """Using the given store, traverses the objects in the
        database to find an object that matches the given path.

        Returns the object up to which the traversal was successful,
        and the part of the path that could not be resolved.

        """

        obj = db.deref(self.obj_path[-1])
        traverser = ITraverser(obj)
        next_obj = traverser.traverse(name, store=db.get_store())

        if not next_obj:
            return False
        else:
            self.path.append(next_obj.name + '/')
            self.obj_path.append(db.ref(next_obj))
            return True


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
        else:
            self.terminal.write('Not implemented\n (%s)' % repr(args))
            return

        data = obj.to_dict()
        if data:
            max_key_len = max(len(key) for key in data)
            for key, value in sorted(data.items()):
                self.terminal.write('%s\t%s\n' % ((key + ':').ljust(max_key_len),
                                                  str(value).encode('utf8')))
