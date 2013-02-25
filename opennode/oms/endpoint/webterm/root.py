import json
import logging
import time
import uuid

from grokcore.component import baseclass, context, name
from twisted.conch.insults.insults import ServerProtocol
from twisted.internet import reactor
from twisted.web.server import NOT_DONE_YET

from opennode.oms.endpoint.httprest.base import HttpRestView
from opennode.oms.endpoint.ssh.protocol import OmsShellProtocol
from opennode.oms.endpoint.webterm.ssh import ssh_connect_interactive_shell
from opennode.oms.model.model.bin import Command

log = logging.getLogger(__name__)

class OmsShellTerminalProtocol(object):
    """Connect a OmsShellProtocol to a web terminal session."""

    def logged_in(self, principal):
        self.principal = principal

    def connection_made(self, terminal, size):
        self.shell = OmsShellProtocol()
        self.shell.set_terminal(terminal)
        self.shell.connectionMade()
        self.shell.terminalSize(size[0], size[1])
        self.shell.logged_in(self.principal)

    def handle_key(self, key):
        self.shell.terminal.dataReceived(key)

    def terminalSize(self, width, height):
        # Insults terminal doesn't work well after resizes
        # also disabled in the oms shell over ssh.
        #
        # self.shell.terminalSize(width, height)
        pass


class SSHClientTerminalProtocol(object):
    """Connect a ssh client session to a web terminal session.
    Can be used to connect to hosts or to services and guis exposed via ssh interfaces, tunnels etc"""

    def logged_in(self, principal):
        self.principal = principal

    def __init__(self, user, host, port=22):
        self.user = user
        self.host = host
        self.port = port

    def connection_made(self, terminal, size):
        self.transport = terminal.transport

        ssh_connect_interactive_shell(self.user, self.host, self.port,
                                      self.transport, self.set_channel, size)

    def set_channel(self, channel):
        self.channel = channel

    def handle_key(self, key):
        self.channel.write(key)

    def terminalSize(self, width, height):
        if callable(getattr(self.channel, 'terminalSize', None)):
            self.channel.terminalSize(width, height)


class WebTransport(object):
    """Used by WebTerminal to actually send the data through the http transport."""

    def __init__(self, session):
        self.session = session

    def write(self, text):
        # Group together writes so that we reduce the number of http roundtrips.
        # Kind of Nagle's algorithm.
        self.session.buffer += text
        reactor.callLater(0.05, self.session.process_queue)

    def loseConnection(self):
        """Close the connection ensuring the the web client will properly detect this close.
        The name of the method was chosen to implement the twisted convention."""
        if self.session.id in TerminalServerMixin.sessions:
            del TerminalServerMixin.sessions[self.session.id]
        self.write('\r\n')


class WebTerminal(ServerProtocol):
    """Used by TerminalProtocols (like OmsShellProtocol) to actually manipulate the terminal."""

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

    def handle_resize(self, size):
        if self.terminal_size != size:
            self.terminal_protocol.terminalSize(size[0], size[1])

    def windowChanged(self, *args):
        """Called back by insults on terminalSize."""
        pass

    def enqueue(self, request):
        self.queue.append(request)
        if self.buffer:
            self.process_queue()

    def process_queue(self):
        # Only one ongoing polling request should be live.
        # But I'm not sure if this can be guaranteed so let's keep temporarily keep them all.
        if self.queue:
            for r in self.queue:
                self.write(r)
            self.queue = []

    def write(self, request):
        # chunk writes because the javascript renderer is very slow
        # this avoids long pauses to the user.
        chunk_size = 4000

        unicode_buffer = self.buffer.decode('utf-8')

        chunk = unicode_buffer[0:chunk_size]

        request.write(json.dumps(dict(session=self.id, data=chunk)))
        request.finish()

        self.buffer = unicode_buffer[chunk_size:].encode('utf-8')

    def __repr__(self):
        return 'TerminalSession(%s, %s, %s, %s)' % (self.id, self.queue, self.buffer, self.timestamp)


class TerminalServerMixin(object):
    """Common code for view-based and twisted-resource based rendering of ShellInABox protocol."""

    sessions = {}

    def render_POST(self, request):
        session_id = request.args.get('session', [None])[0]

        size = (int(request.args['width'][0]), int(request.args['height'][0]))

        # The handshake consists of the session id and initial data to be rendered.
        if not session_id:
            session = TerminalSession(self.get_terminal_protocol(request), size)
            session_id = session.id
            self.sessions[session.id] = session

        if session_id not in self.sessions:
            # Session interruption is defined using a success status
            # but with empty session (that's the protocol, I didn't design it).
            request.setResponseCode(200)
            return json.dumps(dict(session='', data=''))

        session = self.sessions[session_id]
        session.handle_resize(size)

        # There are two types of requests:
        # 1) user type keystrokes, return synchronously
        # 2) long polling requests are suspended until there is activity from the terminal
        keys = request.args.get('keys', None)
        if keys:
            session.handle_keys(keys[0])
            return ""  # responses to this kind of requests are ignored
        else:
            session.enqueue(request)

        return NOT_DONE_YET

    def get_terminal_protocol(self, request):
        protocol = self.terminal_protocol
        protocol.logged_in(request.interaction.participations[0].principal)
        return protocol


class ConsoleView(HttpRestView, TerminalServerMixin):
    baseclass()


class OmsShellConsoleView(ConsoleView):
    context(Command)
    name('webterm')

    @property
    def terminal_protocol(self):
        # TODO: pass the self.context.cmd so that we can execute this particular command
        # instead of hardcoding the oms shell.
        return OmsShellTerminalProtocol()
