class Root(object):
    pass


class ComputeList(object):
    def get_all(self):
        return ['foo', 'bar', 'baz']


class Compute(object):
    def __init__(self, id):
        self.id = id

    def __str__(self):
        return 'Compute %s' % self.id
