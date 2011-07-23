from zope.interface import Interface, implements

from opennode.oms.db import db


class ITraverser(Interface):
    def traverse(name, store):
        pass


class Traverser(object):
    implements(ITraverser)

    def __init__(self, context):
        self.context = context


def traverse_path(obj, path):
    """Using the given store, traverses the objects in the
    database to find an object that matches the given path.

    Returns the object up to which the traversal was successful,
    and the part of the path that could not be resolved.

    """

    if not path:
        return obj

    store = db.get_store()

    path = path.split('/')

    # Allow one extra slash at the end:
    if  path[-1] == '': path.pop()

    ret = [obj]
    while path:
        name = path[0]
        traverser = ITraverser(ret[-1])

        next_obj = traverser.traverse(name, store=store)

        if not next_obj: break

        ret.append(next_obj)
        path = path[1:]

    return ret[1:], path
