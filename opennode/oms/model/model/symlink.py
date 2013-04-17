from __future__ import absolute_import

from .base import Model


class Symlink(Model):
    """Symbolic link

    Permissions are never inherited from parent, always from target.
    """

    def get_annotations(self):
        return self.target.__annotations__

    def set_annotations(self, value):
        self.target.__annotations__ = value

    __annotations__ = property(get_annotations, set_annotations)

    def set_dummy(self, value):
        pass

    def get_inherit_permissions(self):
        return False

    inherit_permissions = property(get_inherit_permissions, set_dummy)

    def __init__(self, name, target):
        self.__name__ = name
        self.target = target

    def __str__(self):
        return 'Symlink(%s)' % self.target


def follow_symlinks(item):
    """Returns the object pointed to a symlink chain."""
    if isinstance(item, Symlink):
        return follow_symlinks(item.target)
    return item
