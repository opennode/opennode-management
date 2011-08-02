import re

from grokcore.component import Adapter, implements
from zope.interface import Interface


__all__ = ['traverse_path', 'traverse1']


class ITraverser(Interface):
    """Classes providing object traversal should implement this interface."""

    def traverse(name, store):
        """Takes the name of the object to traverse to, and a Storm ORM Store instance.

        Implementers must remember to also provide traversal logic for
        the `.` and `..` paths.

        """


class Traverser(Adapter):
    """Base class for all object traversers."""

    implements(ITraverser)


def traverse_path(obj, path):
    """Starting from the given object, traverses all its descendant
    objects to find an object that matches the given path.

    Returns a tuple that contains the object up to which the traversal
    was successful plus all objects that led to that object, and the
    part of the path that could not be resolved.

    """

    if not path or path == '/':
        return [obj], []

    path = re.sub(r'\/+', '/', path)
    if path.endswith('/'):
        path = path[:-1]
    if path.startswith('/'):
        path = path[1:]

    path = path.split('/')

    ret = [obj]
    while path:
        name = path[0]
        try:
            traverser = ITraverser(ret[-1])
        except TypeError:
            break

        next_obj = traverser.traverse(name)

        if not next_obj: break

        ret.append(next_obj)
        path = path[1:]

    return ret[1:], path


def traverse1(path):
    from opennode.oms.zodb import db
    oms_root = db.get_root()['oms_root']
    objs, untraversed_path = traverse_path(oms_root, path)
    if objs and not untraversed_path:
        return objs[-1]
    else:
        return None
