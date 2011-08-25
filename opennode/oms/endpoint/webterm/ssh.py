import os

from twisted.conch.ssh import transport, keys, userauth, connection, channel, common, session
from twisted.internet import defer

class ClientTransport(transport.SSHClientTransport):

    def __init__(self, terminal_transport, set_channel):
        self.terminal_transport = terminal_transport
        self.set_channel = set_channel

    def verifyHostKey(self, pubKey, fingerprint):
        # TODO: check fingerprints?
        return defer.succeed(1)

    def connectionSecure(self):
        self.requestService(ClientUserAuth(os.environ["USER"], ClientConnection(self.terminal_transport, self.set_channel)))


class ClientUserAuth(userauth.SSHUserAuthClient):

    def __init__(self, *args, **kwargs):
        # Super is old-style class
        userauth.SSHUserAuthClient.__init__(self, *args, **kwargs)

        names = ["id_fake_dsa", "id_dsa", "id_rsa"]

        def read(ext):
            home = os.environ["HOME"]
            for base in names:
                name = "%s/.ssh/%s%s" % (home, base, ext)
                if os.path.exists(name):
                    f = open(name, 'r')
                    return f.read()
            return None

        self.publicKey = read('.pub')
        self.privateKey = read('')

    def getPassword(self, prompt = None):
        # this says we won't do password authentication
        return

    def getPublicKey(self):
        return keys.Key.fromString(data = self.publicKey).blob()

    def getPrivateKey(self):
        return defer.succeed(keys.Key.fromString(data = self.privateKey).keyObject)


class ClientConnection(connection.SSHConnection):

    def __init__(self, terminal_transport, set_channel):
        connection.SSHConnection.__init__(self)

        self.terminal_transport = terminal_transport
        self.set_channel = set_channel

    def serviceStarted(self):
        print "TERMINAL TRANSPORT", self.terminal_transport
        self.openChannel(ShellChannel(terminal_transport=self.terminal_transport, conn = self))
        #self.openChannel(ShellChannel(conn = self))

    #def ssh_CHANNEL_DATA(self, packet):
    #   print "GOT CHANNEL DATA", packet
    #   connection.SSHConnection.ssh_CHANNEL_DATA(self, packet)

class ShellChannel(channel.SSHChannel):

    name = 'session'

    def __init__(self, terminal_transport=None, *args, **kwargs):
        # Super is old-style class
        channel.SSHChannel.__init__(self, *args, **kwargs)
        self.terminal_transport = terminal_transport

    def openFailed(self, reason):
        print 'Channel failed', reason

    def channelOpen(self, data):
        self.conn.set_channel(self)

        data = session.packRequest_pty_req('xterm-color', (24, 80, 0, 0), '')
        deferred = self.conn.sendRequest(self, 'pty-req', data, wantReply = 1)

        @deferred
        def on_success(ignored):
            self.conn.sendRequest(self, 'shell', '', wantReply = 1)

    def dataReceived(self, data):
        if self.terminal_transport:
            self.terminal_transport.write(data)

    def closed(self):
        self.loseConnection()