from twisted.python import log

class DetachedProtocol(object):
    """This represents a detached background protocol used to execute commands
    in background and redirect output to logs"""

    def __init__(self):
        self.terminal = self
        self.path = ['']
        self.use_security_proxy = False
        self.write_buffer = []

    def write(self, *args, **kwargs):
        self.write_buffer.append(''.join(map(str, args)))
        log.msg("DETACHED: %s" % self.write_buffer, system='omsh-detached', **kwargs)
