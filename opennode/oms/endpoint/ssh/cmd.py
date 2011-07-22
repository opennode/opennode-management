from twisted.internet import defer

from opennode.oms import db
from opennode.oms.model.traversal import ITraverser


class Cmd(object):
    def __init__(self, protocol):
        self.protocol = protocol



class cmd_cd(Cmd):

    @defer.inlineCallbacks
    def __call__(self, *args):
        if len(args) > 1:
            raise Exception('cd takes at most 1 argument')
        else:
            path = args[0] if args else None

        for name in path.split('/'):
            success = yield defer.maybeDeferred(self._do_cmd, name)
            if not success:
                self.protocol.terminal.write('No such file or directory: %s' % name)
                self.protocol.terminal.nextLine()
                break

    def _do_cmd(self, name):
        if not name:
            self.protocol.path = [self.protocol.path[0]]
            self.protocol.obj_path = [self.protocol.obj_path[0]]
        elif name == '..':
            if len(self.protocol.path) > 1:
                self.protocol.path.pop()
                self.protocol.obj_path.pop()
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

        obj = self.protocol.obj_path[-1]
        traverser = ITraverser(obj)
        next_obj = traverser.traverse(name, store=db.get_store())

        if not next_obj:
            return False
        else:
            self.protocol.path.append(next_obj.name + '/')
            self.protocol.obj_path.append(next_obj)
            return True
