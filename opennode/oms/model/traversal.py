from zope.interface import Interface, implements

from opennode.oms.db import db


class ITraverser(Interface):
    """Classes providing object traversal should implement this interface."""

    def traverse(name, store):
        """Takes the name of the object to traverse to, and a Storm ORM Store instance.

        Implementers must remember to also provide traversal logic for
        the `.` and `..` paths.

        """


class Traverser(object):
    """Base class for all object traversers."""

    implements(ITraverser)

    def __init__(self, context):
        self.context = context


def traverse_path(obj, path):
    """Starting from the given object, traverses all its descendant
    objects to find an object that matches the given path.

    Returns a tuple that contains the object up to which the traversal
    was successful plus all objects that led to that object, and the
    part of the path that could not be resolved.

    """

    if not path:
        return [obj], ''

    store = db.get_store()

    if path.endswith('/'):
        path = path[:-1]
    path = path.split('/')

    ret = [obj]
    while path:
        name = path[0]
        traverser = ITraverser(ret[-1])

        next_obj = traverser.traverse(name, store=store)

        if not next_obj: break

        ret.append(next_obj)
        path = path[1:]

    return ret[1:], path
