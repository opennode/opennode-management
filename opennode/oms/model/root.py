from opennode.oms.model.model import ComputeList, SingletonModel


class Root(SingletonModel):
    name = ''
    children = {'compute': ComputeList,}

    def __str__(self):
        return 'OMS root'

    @property
    def parent(self):
        return self
