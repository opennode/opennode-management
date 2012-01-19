from grokcore.security import Permission, name, title, description
from zope.securitypolicy.role import Role as ZopeRole


class Role(ZopeRole):
    """Oms roles act as permissions"""

    nick_to_role = {}
    role_to_nick = {}

    def __init__(self, name, nick):
        super(Role, self).__init__(name, name)
        self.nick = nick

        if nick:
            self.nick_to_role[nick] = self
            self.role_to_nick[self.id] = nick


class Nothing(Permission):
    name('oms.nothing')
    title('No permissions')
    description('Every user has this permission, even anonymous')


class Read(Permission):
    name('read')


class Modify(Permission):
    name('modify')


class Create(Permission):
    name('create')


class Add(Permission):
    name('add')


class View(Permission):
    name('view')


class Rest(Permission):
    name('rest')
    description('Used to allow access on rest API')
