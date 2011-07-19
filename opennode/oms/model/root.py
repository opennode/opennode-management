from opennode.oms.model.model import Model, ComputeList


class Root(Model):

    def __getitem__(self, key):
        if key == 'compute':
            return ComputeList()

    def __str__(self):
        return 'OMS root'
