from opennode.oms.model.model import Model, ComputeList


class Root(Model):
    name = ''
    children = {'compute': ComputeList,}

    def __str__(self):
        return 'OMS root'

    @property
    def parent(self):
        return self
