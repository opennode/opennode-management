import re

from twisted.conch import recvline
from twisted.internet import defer

from opennode.oms.endpoint.ssh import cmd
from opennode.oms.zodb import db

class OmsSshProtocol(recvline.HistoricRecvLine):
    """Simple echo protocol.

    Accepts lines of input and writes them back to its connection.  If
    a line consisting solely of "quit" is received, the connection
    is dropped.

    """

    def __init__(self):
        super(OmsSshProtocol, self).__init__()
        self.path = ['']
        # self.obj_path will be initialised in connectionMade

    @defer.inlineCallbacks
    def connectionMade(self):
        super(OmsSshProtocol, self).connectionMade()
        self.obj_path = yield db.transact(lambda: [db.ref(db.get_root()['oms_root'])])

    def lineReceived(self, line):
        line = line.strip()

        if line == 'quit':
            self.terminal.loseConnection()
            return

        cmd_name, cmd_args = line.partition(' ')[::2]
        cmd_handler = getattr(cmd, 'cmd_' + cmd_name, None)
        if cmd_handler:
            cmd_args = cmd_args.strip()
            if cmd_args:
                cmd_args = re.split(r'\s+', cmd_args)
            else:
                cmd_args = []
            deferred = defer.maybeDeferred(cmd_handler(self), *cmd_args)
        else:
            if line:
                self.terminal.write('No such command: %s' % cmd_name)
                self.terminal.nextLine()
            deferred = defer.Deferred()
            deferred.callback(None)

        @deferred
        def on_success(ret):
            self.terminal.write(self.ps[self.pn])

        @deferred
        def on_error(f):
            f.printDetailedTraceback(self.terminal)
            self.terminal.nextLine()
            self.terminal.write(self.ps[self.pn])

        ret = defer.Deferred()
        deferred.addBoth(ret.callback)
        return ret

    @property
    def ps(self):
        ps1 = '%s@%s:%s%s ' % ('user', 'oms', self._cwd(), '#')
        return [ps1, '... ']

    def _cwd(self):
        return self.make_path(self.path)

    @staticmethod
    def make_path(path):
        return '/'.join(path) or '/'
