from zope.authentication.interfaces import IAuthentication
from zope.component import getUtility
from zope.interface import implements
from zope.security.interfaces import IPrincipal, IInteraction


class User(object):
    implements(IPrincipal)

    def __init__(self, id):
        self.id = id
        self.groups = []

    def __repr__(self):
        return '%s (%s)' % (type(self), self.id)


class Group(User):
    pass


def effective_principals(principal_or_interaction, acc=None):
    """Returns all the principals including recursive groups"""

    if acc is None:
        acc = []

    if IInteraction.providedBy(principal_or_interaction):
        for i in principal_or_interaction.participations:
            effective_principals(i.principal, acc)
    else:
        auth = getUtility(IAuthentication, context=None)

        acc.append(principal_or_interaction)
        for i in principal_or_interaction.groups:
            effective_principals(auth.getPrincipal(i), acc)

    return acc
