import logging
import re

from grokcore.component import Adapter, implements, baseclass
from zope.interface import Interface

from opennode.oms.model.model.symlink import follow_symlinks


__all__ = ['traverse_path', 'traverse1']


log = logging.getLogger(__name__)


class ITraverser(Interface):
    """Adapters providing object traversal should implement this interface."""

    def traverse(name):
        """Takes the name of the object to traverse to and returns the traversed object, if any."""


class Traverser(Adapter):
    """Base class for all object traversers."""
    implements(ITraverser)
    baseclass()


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

        next_obj = follow_symlinks(traverser.traverse(name))

        if not next_obj:
            break

        ret.append(next_obj)
        path = path[1:]

    return ret[1:], path


def traverse1(path):
    """Provides a shortcut for absolute path traversals without
    needing to pass in the root object.

    """

    # Do it here just in case; to avoid circular imports:
    from opennode.oms.zodb import db

    oms_root = db.get_root()['oms_root']
    objs, untraversed_path = traverse_path(oms_root, path)
    if objs and not untraversed_path:
        return objs[-1]
    else:
        return None


def canonical_path(item):
    path = []
    from opennode.oms.security.authentication import Sudo
    while item:
        with Sudo(item):
            assert item.__name__ is not None, '%s.__name__ is None' % item
            item = follow_symlinks(item)
            path.insert(0, item.__name__)
            item = item.__parent__
    return '/'.join(path)
