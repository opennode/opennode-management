from opennode.oms.config import get_config

from twisted.python import log

class DetachedProtocol(object):
    """This represents a detached background protocol used to execute commands
    in background and redirect output to logs"""

    def __init__(self):
        self.terminal = self
        self.path = ['']
        self.use_security_proxy = False

    def write(self, *args, **kwargs):
        data = ''.join(map(str, args))
        if get_config().getboolean('general', 'log_detached', False):
            log.msg("DETACHED: %s" % data, system='omsh-detached', **kwargs)
