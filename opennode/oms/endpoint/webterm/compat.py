import os

from twisted.web import resource

from opennode.oms.endpoint.webterm.root import TerminalServerMixin, OmsShellTerminalProtocol, SSHClientTerminalProtocol


class TerminalServer(resource.Resource, TerminalServerMixin):
    """Web resource which handles web terminal sessions adhering to ShellInABox.js protocol.
    NOTE: This is only for backward compatibility.
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

        self.terminal_protocol = terminal_protocol

    def render_POST(self, request):
        # Allow for cross-domain, at least for testing.
        # Normally added by HttpRestServer, but this is a backward compat layer.
        request.responseHeaders.addRawHeader('Access-Control-Allow-Origin', '*')
        return TerminalServerMixin.render_POST(self, request)


class WebTerminalServer(resource.Resource):
    """ShellInABox web terminal protocol handler."""

    isLeaf = False

    def getChild(self, name, request):
        """For now the only mounted terminal service is the commadnline oms management.
        We'll mount here the ssh consoles to machines."""
        if name == 'management':
            return TerminalServer(OmsShellTerminalProtocol())
        if name == 'test_ssh':
            #return self.ssh_test
            # TODO: takes the user name from whatever the user chooses
            # commonly it will be root.
            user = os.environ["USER"]

            # TODO: take the hostname from the model, localhost is for testing
            host = 'localhost'
            return TerminalServer(SSHClientTerminalProtocol(user, host))
        if name == 'test_arbitrary':
            user = request.args['user'][0]
            host = request.args['host'][0]
            return TerminalServer(SSHClientTerminalProtocol(user, host))
        return self

    def __init__(self, avatar=None):
        # Twisted Resource is a not a new style class, so emulating a super-call.
        resource.Resource.__init__(self)
        self.avatar = avatar

    def render(self, request):
        return ""
