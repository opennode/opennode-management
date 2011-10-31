from __future__ import absolute_import

from zope import schema
from zope.interface import Interface, implements

from .base import Model, Container


class IConsole(Interface):
    """Console node."""


class ITextualConsole(Interface):
    """Textual console."""


class IGraphicalConsole(Interface):
    """Graphical console."""


class ITtyConsole(IConsole):
    pty = schema.TextLine(title=u"pty")


class ISshConsole(IConsole):
    user = schema.TextLine(title=u"user")
    hostname = schema.TextLine(title=u"hostname")
    port = schema.Int(title=u"port")


class IVncConsole(IConsole):
    hostname = schema.TextLine(title=u"hostname")
    port = schema.Int(title=u"port")


class TtyConsole(Model):
    implements(ITtyConsole, ITextualConsole)


class TtyConsole(Model):
    implements(ITtyConsole, ITextualConsole)

    def __init__(self, name, pty):
        self.__name__ = name
        self.pty = pty


class SshConsole(Model):
    implements(ISshConsole, ITextualConsole)

    def __init__(self, name, user, hostname, port):
        self.__name__ = name
        self.user = user
        self.hostname = hostname
        self.port = port


class VncConsole(Model):
    implements(IVncConsole, IGraphicalConsole)

    def __init__(self, hostname, port):
        self.__name__ = 'vnc'
        self.hostname = hostname
        self.port = port


class Consoles(Container):
    __name__ = 'consoles'
