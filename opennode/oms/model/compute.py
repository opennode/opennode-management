from opennode.oms.model.base import Model


class ComputeList(Model):

    def get_all(self):
        return [Compute(i) for i in [1, 2, 3, 4, 5]]

    def __getitem__(self, key):
        try:
            compute_id = int(key)
            if compute_id < 0:
                raise ValueError()
        except ValueError:
            return None
        else:
            for compute in self.get_all():
                if compute.id == compute_id:
                    return compute
            return None


class Compute(Model):
    id = None
    architecture = None # 'x86' | 'x64'
    hostname = None
    speed = None # 2.1 GHz
    memory = None # 2.1 GiB
    state = None # 'active' | 'inactive' | 'suspended'

    def __init__(self, id):
        self.id = id

    def __str__(self):
        return 'Compute %s' % self.id
