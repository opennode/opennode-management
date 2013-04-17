from twisted.python import log
from zope.authentication.interfaces import IAuthentication
from zope.component import getUtility

from opennode.oms.config import get_config
from opennode.oms.security.interaction import new_interaction


class DetachedProtocol(object):
    """This represents a detached background protocol used to execute commands
    in background and redirect output to logs"""

    def __init__(self, interaction=None):
        self.terminal = self
        self.protocol = self
        self.path = ['']
        self.use_security_proxy = False
        if interaction is None:
            auth = getUtility(IAuthentication)
            self.interaction = new_interaction(auth.getPrincipal('root'))
        else:
            self.interaction = interaction

    @property
    def principal(self):
        return self.interaction.participations[0].principal

    def write(self, *args, **kwargs):
        data = ''.join(map(str, args))
        if get_config().getboolean('general', 'log_detached', False):
            log.msg("DETACHED: %s" % data, system='omsh-detached', **kwargs)
