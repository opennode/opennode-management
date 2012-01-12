from zope.security.interfaces import IPrincipal

from zope.interface import implements


class User(object):
    implements(IPrincipal)

    def __init__(self, id):
        self.id = id
        self.groups = []

    def __repr__(self):
        return '%s (%s)' % (type(self), self.id)
