from __future__ import absolute_import

from zope.interface import Interface, implements

from .base import Model, ReadonlyContainer


class ITask(Interface):
    """Executable command object."""


class Task(Model):
    implements(ITask)

    def __init__(self, name, parent, cmd):
        self.__name__ = name
        self.__parent__ = parent
        self.cmd = cmd


class Proc(ReadonlyContainer):
    __contains__ = ITask
    __name__ = 'proc'

    def __str__(self):
        return 'Tasks'

    def content(self):
        return {}
