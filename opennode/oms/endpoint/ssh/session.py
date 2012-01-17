from twisted.conch import interfaces as iconch
from twisted.conch.manhole_ssh import TerminalSession, TerminalSessionTransport, TerminalRealm, TerminalUser
from twisted.conch.insults import insults
from twisted.internet import defer

from opennode.oms.endpoint.ssh.protocol import OmsShellProtocol
from opennode.oms.security.principals import User


class BatchOmsShellProtocol(OmsShellProtocol):
    batch = True

    def lineReceived(self, line):
        """Ignore input, we are not a shell"""
        pass


class OmsTerminalSession(TerminalSession):
    def execCommand(self, proto, cmd):
        try:
            chained_protocol = insults.ServerProtocol(BatchOmsShellProtocol)
            self.transportFactory(
                proto, chained_protocol,
                iconch.IConchUser(self.original),
                80, 25)
        except Exception as e:
            print e

        oms_protocol = chained_protocol.terminalProtocol

        @defer.inlineCallbacks
        def spawn_command():
            yield oms_protocol.spawn_command(cmd)
            proto.processEnded()

        spawn_command()


class OmsTerminalSessionTransport(TerminalSessionTransport):
    def __init__(self, proto, chainedProtocol, avatar, width, height):
        TerminalSessionTransport.__init__(self, proto, chainedProtocol, avatar, width, height)

        chainedProtocol.terminalProtocol.logged_in(avatar.principal)


class OmsTerminalRealm(TerminalRealm):
    def __init__(self):
        TerminalRealm.__init__(self)

        def chainProtocolFactory():
            return insults.ServerProtocol(OmsShellProtocol)

        def userFactory(original, avatarId):
            user = TerminalUser(original, avatarId)
            user.principal = User(avatarId)
            return user

        self.chainedProtocolFactory = chainProtocolFactory
        self.sessionFactory = OmsTerminalSession
        self.userFactory = userFactory
        self.transportFactory = OmsTerminalSessionTransport
