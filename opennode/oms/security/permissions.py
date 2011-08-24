from grokcore.security import Permission, name, title, description

class Read(Permission):
    name('read')


class Modify(Permission):
    name('modify')


class Create(Permission):
    name('create')


class Add(Permission):
    name('add')
