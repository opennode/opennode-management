from opennode.oms.model.compute import ComputeList
from opennode.oms.model.base import Model


class Root(Model):

    def __getitem__(self, key):
        if key == 'compute':
            return ComputeList()

    def __str__(self):
        return 'OMS root'
