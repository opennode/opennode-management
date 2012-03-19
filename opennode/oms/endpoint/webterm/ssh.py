import os

from twisted.conch.ssh import transport, keys, userauth, connection, channel, session, common
from twisted.internet import defer, reactor, protocol


def ssh_connect_interactive_shell(user, host, port, transport, set_channel, size, command=None):
    if host == '0.0.0.0':
        raise Exception("invalid ip address '%s'" % host)
    protocol.ClientCreator(reactor, SSHClientTransport, transport, set_channel, size, user, host, command).connectTCP(host, port)


class SSHClientTransport(transport.SSHClientTransport):
    """Performs a SSH connection to a server."""

    def __init__(self, terminal_transport, set_channel, terminal_size, user, host, command):
        self.terminal_transport = terminal_transport
        self.set_channel = set_channel
        self.terminal_size = terminal_size
        self.user = user
        self.host = host
        self.command = command

    def verifyHostKey(self, pubKey, fingerprint):
        # TODO: check fingerprints?
        return defer.succeed(1)

    def connectionSecure(self):
        self.requestService(ClientUserAuth(self.user, SSHShellConnection(self.terminal_transport, self.set_channel, self.terminal_size, self.command)))

    def connectionLost(self, reason):
        transport.SSHClientTransport.connectionLost(self, reason)
        self.terminal_transport.loseConnection()


class ClientUserAuth(userauth.SSHUserAuthClient):
    """Performs ssh connection authentication on behalf of a SSHClientTransport.

    Public key authentication is designed to be performed with the OMS service key.
    The OMS thus takes the responsibility to authorize a given principal and then
    logs in on his behalf.

    """

    def __init__(self, *args, **kwargs):
        """Read the pub/priv keys from the standard location of the OMS home directory."""
        # Super is old-style class
        userauth.SSHUserAuthClient.__init__(self, *args, **kwargs)

        names = ['id_oms_dsa', 'id_oms_rsa', 'id_fake_dsa', 'id_fake_rsa', 'id_dsa', 'id_rsa']

        def read(ext):
            home = os.environ['HOME']
            for base in names:
                name = '%s/.ssh/%s%s' % (home, base, ext)
                if os.path.exists(name):
                    f = open(name, 'r')
                    return f.read()
            return None

        self.publicKey = read('.pub')
        self.privateKey = read('')

    def getPublicKey(self):
        """Return the public key unless we already failed our previous publickey auth attempt."""
        if self.lastAuth == 'publickey':
            return None
        return keys.Key.fromString(data=self.publicKey).blob()

    def getPrivateKey(self):
        return defer.succeed(keys.Key.fromString(data=self.privateKey).keyObject)

    def getPassword(self, prompt=None):
        """Conch expects a deferred which will yield a password to try.
        Writes a prompt and redirect the terminal input to a password reader which will
        callback a deferred and thus yield a password to conch.

        The terminal input will be automatically handled over to the ssh channel
        after successful authentication.

        """

        terminal = self.transport.terminal_transport
        terminal.write("%s@%s's password: " % (self.user, self.transport.host))

        deferred_password = defer.Deferred()

        class PasswordReader(object):
            def __init__(self):
                self.password = ""

            def write(self, ch):
                if ch == '\x7f':
                    self.password = self.password[:-1]
                elif ch == '\r':
                    if not deferred_password.called:
                        deferred_password.callback(self.password)
                        terminal.write('\r\n')
                else:
                    self.password += ch

        self.transport.set_channel(PasswordReader())
        return deferred_password


class SSHShellConnection(connection.SSHConnection):
    """Represents a SSH client connection opening a interactive remote shell."""

    def __init__(self, terminal_transport, set_channel, terminal_size, command):
        connection.SSHConnection.__init__(self)

        self.terminal_transport = terminal_transport
        self.set_channel = set_channel
        self.terminal_size = terminal_size
        self.command = command

    def serviceStarted(self):
        self.openChannel(ShellChannel(conn=self))


class ShellChannel(channel.SSHChannel):
    """This is the core of the interactive ssh shell.

    """
    name = 'session'

    def __init__(self, *args, **kwargs):
        # Super is old-style class
        channel.SSHChannel.__init__(self, *args, **kwargs)
        self.terminal_transport = self.conn.terminal_transport

    def channelOpen(self, data):
        self.conn.set_channel(self)

        data = session.packRequest_pty_req('xterm-color', (self.conn.terminal_size[1], self.conn.terminal_size[0], 0, 0), '')
        deferred = self.conn.sendRequest(self, 'pty-req', data, wantReply=1)

        @deferred
        def on_success(ignored):
            if self.conn.command:
                self.conn.sendRequest(self, 'exec', common.NS(self.conn.command), wantReply=1)
            else:
                self.conn.sendRequest(self, 'shell', '', wantReply=1)

    def dataReceived(self, data):
        if self.terminal_transport:
            self.terminal_transport.write(data)

    def closed(self):
        self.terminal_transport.loseConnection()
        self.loseConnection()

    def terminalSize(self, width, height):
        data = session.packRequest_window_change((height, width, 0, 0))
        self.conn.sendRequest(self, 'window-change', data, wantReply=0)
