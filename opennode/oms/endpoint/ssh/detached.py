from twisted.python import log

class DetachedProtocol(object):
    """This represents a detached background protocol used to execute commands
    in background and redirect output to logs"""

    def __init__(self):
        self.terminal = self

    def write(self, *args, **kwargs):
        log.msg("SYSLOG: %s" % args, system='ssh-detached', **kwargs)
