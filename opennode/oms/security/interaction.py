from zope.authentication.interfaces import IAuthentication
from zope.component import getUtility
from zope.securitypolicy.zopepolicy import ZopeSecurityPolicy


class SessionStub(object):
    def __init__(self, principal=None):
        self.principal = principal
        self.interaction = None


def new_interaction(principal):
    auth = getUtility(IAuthentication, context=None)

    interaction = ZopeSecurityPolicy()
    sess = SessionStub(auth.getPrincipal(principal))
    interaction.add(sess)
    return interaction
