from twisted.conch import interfaces as iconch
from twisted.conch.manhole_ssh import TerminalSession, TerminalSessionTransport, TerminalRealm, TerminalUser
from twisted.conch.ssh.session import SSHSession
from twisted.conch.insults import insults
from twisted.internet import defer
from zope.authentication.interfaces import IAuthentication
from zope.component import getUtility

from opennode.oms.endpoint.ssh.protocol import OmsShellProtocol


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
            yield oms_protocol.spawn_commands(cmd)
            if oms_protocol.last_error:
                yield oms_protocol.spawn_command('last_error')
            proto.processEnded()

        spawn_command()


class OmsTerminalSessionTransport(TerminalSessionTransport):
    def __init__(self, proto, chainedProtocol, avatar, width, height):
        TerminalSessionTransport.__init__(self, proto, chainedProtocol, avatar, width, height)

        chainedProtocol.terminalProtocol.logged_in(avatar.principal)


class OmsSSHSession(SSHSession):
    def __init__(self, *args, **kw):
        SSHSession.__init__(self, *args, **kw)
        self.__dict__['request_auth_agent_req@openssh.com'] = self.request_agent

    def request_x11_req(self, data):
        return 0

    def request_env(self, data):
        return 0

    def request_agent(self, data):
        return 0


class OmsTerminalUser(TerminalUser):
    def __init__(self, original, avatarId):
        TerminalUser.__init__(self, original, avatarId)
        self.channelLookup['session'] = OmsSSHSession


class OmsTerminalRealm(TerminalRealm):
    def __init__(self):
        TerminalRealm.__init__(self)

        def userFactory(original, avatarId):
            user = OmsTerminalUser(original, avatarId)

            auth = getUtility(IAuthentication, context=None)
            user.principal = auth.getPrincipal(avatarId)
            return user

        self.chainedProtocolFactory = lambda: insults.ServerProtocol(OmsShellProtocol)
        self.sessionFactory = OmsTerminalSession
        self.userFactory = userFactory
        self.transportFactory = OmsTerminalSessionTransport
