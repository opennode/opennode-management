from __future__ import absolute_import

from grokcore.component import context, baseclass
from zope import schema
from zope.component import provideSubscriptionAdapter
from zope.interface import Interface, implements

from .actions import ActionsContainerExtension, Action, action
from .base import Container, ReadonlyContainer


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


class TtyConsole(ReadonlyContainer):
    implements(ITtyConsole, ITextualConsole)


class TtyConsole(ReadonlyContainer):
    implements(ITtyConsole, ITextualConsole)

    def __init__(self, name, pty):
        self.__name__ = name
        self.pty = pty


class SshConsole(ReadonlyContainer):
    implements(ISshConsole, ITextualConsole)

    def __init__(self, name, user, hostname, port):
        self.__name__ = name
        self.user = user
        self.hostname = hostname
        self.port = port


class VncConsole(ReadonlyContainer):
    implements(IVncConsole, IGraphicalConsole)

    def __init__(self, hostname, port):
        self.__name__ = 'vnc'
        self.hostname = hostname
        self.port = port


class Consoles(Container):
    __name__ = 'consoles'


class AttachAction(Action):
    """Attach to textual console"""
    baseclass()

    action('attach')

    def execute(self, cmd, args):
        cmd.write("not implemented yet\n")


class SshAttachAction(AttachAction):
    context(ISshConsole)


class TtyAttachAction(AttachAction):
    context(ISshConsole)


provideSubscriptionAdapter(ActionsContainerExtension, adapts=(IConsole, ))
