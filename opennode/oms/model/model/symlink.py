from __future__ import absolute_import

from zope import schema
from zope.interface import Interface, implements

from .base import Model, Container


class ISymlink(Interface):
    """Symbolic link."""

class Symlink(Model):
    implements(ISymlink)

    def __init__(self, name, target):
        self.__name__ = name
        self.target = target
