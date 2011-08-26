import json
import os
import time
import uuid

from twisted.conch.insults.insults import ServerProtocol
from twisted.internet import reactor
from twisted.web import resource
from twisted.web.server import NOT_DONE_YET

from opennode.oms.endpoint.ssh.protocol import OmsSshProtocol
from opennode.oms.endpoint.webterm.ssh import ssh_connect_interactive_shell


class OmsShellTerminalProtocol(object):
    """Connect a OmsSshProtocol to a web terminal session."""

    def connection_made(self, terminal, size):
        self.shell = OmsSshProtocol()
        self.shell.terminal = terminal
        self.shell.terminal.terminalProtocol = self.shell
        self.shell.connectionMade()

    def handle_key(self, key):
        self.shell.terminal.dataReceived(key)


class SSHClientTerminalProtocol(object):
    """Connect a ssh client session to a web terminal session."""

    def __init__(self, user, host, port=22):
        self.user = user
        self.host = host
        self.port = port

    def connection_made(self, terminal, size):
        self.transport = terminal.transport

        ssh_connect_interactive_shell(self.user, self.host, self.port, self.transport, self.set_channel, size)

    def set_channel(self, channel):
        self.channel = channel

    def handle_key(self, key):
        self.channel.write(key)


class WebTransport(object):
    """Used by WebTerminal to actually send the data through the http transport."""

    def __init__(self, session):
        self.session = session

    def write(self, text):
        # Group together writes so that we reduce the number of http roundtrips.
        # Kind of Nagle's algorithm.
        self.session.buffer += text
        reactor.callLater(0.05, self.session.processQueue)


class WebTerminal(ServerProtocol):
    """Used by TerminalProtocols (like OmsSshProtocol) to actually manipulate the terminal."""

    def __init__(self, session):
        ServerProtocol.__init__(self)
        self.session = session
        self.transport = WebTransport(session)


class TerminalSession(object):
    """A session for our ajax terminal emulator."""

    def __init__(self, terminal_protocol, terminal_size):
        self.id = str(uuid.uuid4())
        self.queue = []
        self.buffer = ""

        # TODO: handle session timeouts
        self.timestamp = time.time()

        self.terminal_size = terminal_size

        self.terminal_protocol = terminal_protocol
        self.terminal_protocol.connection_made(WebTerminal(self), terminal_size)

    def parse_keys(self, key_stream):
        """The ajax protocol encodes keystrokes as a string of hex bytes,
        so each char code occupies to characters in the encoded form."""
        while key_stream:
            yield chr(int(key_stream[0:2], 16))
            key_stream = key_stream[2:]

    def handle_keys(self, key_stream):
        """Send each input key the terminal."""
        for key in self.parse_keys(key_stream):
            self.terminal_protocol.handle_key(key)

    def enqueue(self, request):
        self.queue.append(request)
        if self.buffer:
            self.processQueue()

    def processQueue(self):
        # Only one ongoing polling request should be live.
        # But I'm not sure if this can be guaranteed so let's keep temporarily keep them all.
        if self.queue:
            for r in self.queue:
                self.write(r)
            self.queue = []

    def write(self, request):
        # chunk writes because the javascript renderer is very slow
        # this avoids long pauses to the user.
        chunk_size = 100

        unicode_buffer = self.buffer.decode('utf-8')

        chunk = unicode_buffer[0:chunk_size]

        request.write(json.dumps(dict(session=self.id, data=chunk)))
        request.finish()

        self.buffer = unicode_buffer[chunk_size:].encode('utf-8')

    def __repr__(self):
        return 'TerminalSession(%s, %s, %s, %s)' % (self.id, self.queue, self.buffer, self.timestamp)


class TerminalServer(resource.Resource):
    """Web resource which handles web terminal sessions adhering to ShellInABox.js protocol.

    """

    def render_OPTIONS(self, request):
        """Return headers which allow cross domain xhr for this."""
        headers = request.responseHeaders
        headers.addRawHeader('Access-Control-Allow-Origin', '*')
        headers.addRawHeader('Access-Control-Allow-Methods', 'POST, OPTIONS')
        # this is necessary for firefox
        headers.addRawHeader('Access-Control-Allow-Headers', 'Origin, Content-Type, Cache-Control')
        # this is to adhere to the OPTIONS method, not necessary for cross-domain
        headers.addRawHeader('Allow', 'GET, POST, OPTIONS')

        return ""

    def __init__(self, terminal_protocol, avatar=None):
        # Twisted Resource is a not a new style class, so emulating a super-call.
        resource.Resource.__init__(self)

        self.sessions = {}
        self.terminal_protocol = terminal_protocol

    def render_POST(self, request):
        # Allow for cross-domain, at least for testing.
        request.responseHeaders.addRawHeader('Access-Control-Allow-Origin', '*')

        session_id = request.args.get('session', [None])[0]

        # The handshake consists of the session id and initial data to be rendered.
        if not session_id:
            size = (int(request.args['width'][0]), int(request.args['height'][0]))
            session = TerminalSession(self.terminal_protocol, size)
            session_id = session.id
            self.sessions[session.id] = session

        if not self.sessions.has_key(session_id):
            request.setResponseCode(500)
            return "no such session " + session_id

        session = self.sessions[session_id]

        # There are two types of requests:
        # 1) user type keystrokes, return synchronously
        # 2) long polling requests are suspended until there is activity from the terminal
        keys = request.args.get('keys', None)
        if keys:
            session.handle_keys(keys[0])
            return "" # responsed to this kind of requests are ignored
        else:
            session.enqueue(request)

        return NOT_DONE_YET


class WebTerminalServer(resource.Resource):
    """ShellInABox web terminal protocol handler."""

    isLeaf = False

    def getChild(self, name, request):
        """For now the only mounted terminal service is the commadnline oms management.
        We'll mount here the ssh consoles to machines."""
        if name == 'management':
            return self.management
        if name == 'test_ssh':
            return self.ssh_test
        return self

    def __init__(self, avatar=None):
        # Twisted Resource is a not a new style class, so emulating a super-call.
        resource.Resource.__init__(self)
        self.avatar = avatar

        self.management = TerminalServer(OmsShellTerminalProtocol())

        # TODO: takes the user name from whatever the user chooses
        # commonly it will be root.
        user = os.environ["USER"]

        # TODO: take the hostname from the model, localhost is for testing
        host = 'localhost'
        self.ssh_test = TerminalServer(SSHClientTerminalProtocol(user, host))

    def render(self, request):
        return ""
