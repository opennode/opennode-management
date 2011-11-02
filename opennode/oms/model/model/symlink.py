from __future__ import absolute_import

from .base import Model


class Symlink(Model):
    """Symbolic link."""

    def __init__(self, name, target):
        self.__name__ = name
        self.target = target

def follow_symlinks(item):
    """Returns the object pointed to a symlink chain."""
    if isinstance(item, Symlink):
        return follow_symlinks(item.target)
    return item
