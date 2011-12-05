class DetachedProtocol(object):
    """This represents a detached background protocol used to execute commands
    in background and redirect output to logs"""

    def write(self, *args):
        """Currently nop"""
        print "SYSLOG:", args
