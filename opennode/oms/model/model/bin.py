from __future__ import absolute_import

from zope.interface import Interface, implements

from .base import Model, ReadonlyContainer


class ICommand(Interface):
    """Executable command object."""


class Command(Model):
    implements(ICommand)

    def __init__(self, name, parent, cmd):
        self.__name__ = name
        self.__parent__ = parent
        self.cmd = cmd


class Bin(ReadonlyContainer):
    __contains__ = Command
    __name__ = 'bin'

    def __str__(self):
        return 'Commands'

    def content(self):
        # circular import
        from opennode.oms.endpoint.ssh.cmd import registry

        return dict((name, Command(name, self, cmd)) for name, cmd in registry.commands().items() if name)
