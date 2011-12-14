from grokcore.security import Permission, name, title, description


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


class Rest(Permission):
    name('rest')
    description('Used to allow access on rest API')
