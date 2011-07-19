
from storm.locals import Int, Unicode, Float
from storm.references import ReferenceSet, Reference
from storm.base import Storm

from opennode.oms import db


class Model(Storm):
    def __getitem__(self, key):
        return None


class Template(Model):
    __storm_table__ = 'template'
    id = Int(primary=True)
    name = Unicode()
    base_type = Unicode() # Ubuntu|Redhat|Custom|Windows
    min_cores = Int()
    max_cores = Int()
    min_memory = Int()
    max_memory = Int()
    computes = ReferenceSet(id, 'Compute.template_id')


class ComputeList(Model):

    def get_all(self):
        return db.get_store().find(Compute)

    def __getitem__(self, key):
        try:
            compute_id = int(key)
            if compute_id < 0:
                raise ValueError()
        except ValueError:
            return None
        else:
            return db.get_store().get(Compute, compute_id)


class Compute(Model):
    __storm_table__ = 'compute'
    id = Int(primary=True)
    architecture = Unicode() # 'x86' | 'x64'
    hostname = Unicode()
    speed = Float() # 2.1 GHz
    memory = Float() # 2.1 GiB
    state = Unicode() # 'active' | 'inactive' | 'suspended'
    template_id = Int()
    template = Reference(template_id, Template.id)
    network_devices = ReferenceSet(id, 'NetworkDevice.compute_id')


class Network(Model):
    __storm_table__ = 'network'
    id = Int(primary=True)
    vlan = Unicode()
    label = Unicode()
    state = Unicode()

    # ip-network
    ipv4_address_range = Unicode()
    ipv4_gateway = Unicode()
    ipv6_address_range = Unicode()
    ipv6_gateway = Unicode()
    allocation = Unicode() # dynamic | static
    devices = ReferenceSet(id, 'NetworkDevice.network_id')


class NetworkDevice(Model):
    __storm_table__ = 'network_device'
    id = Int(primary=True)
    interface = Unicode()
    mac = Unicode()
    state = Unicode() # active | inactive
    network_id = Int()
    network = Reference(network_id, Network.id)
    compute_id = Int()
    compute = Reference(compute_id, Compute.id)


class Storage(Model):
    __storm_table__ = 'storage'
    id = Int(primary=True)
    size = Float() # 1.1 GiB
    state = Unicode() # online | offline | backup | snapshot | resize | degraded


class Tag(Model):
    __storm_table__ = 'tag'
    id = Int(primary=True)
    name = Unicode()



