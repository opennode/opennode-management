from storm.base import Storm
from storm.locals import Int, Unicode, Float
from storm.references import ReferenceSet, Reference

from opennode.oms.db import db


class Model(Storm):
    """Base class for all models.

    Provides generic implementations for:
      * child traversal
      * listing of contained content
      * serialisation to simple Python dicts
      * computation of paths

    In addition, classes inheriting from this base class must
    implement a 'name' and 'parent' property for traversal and
    computation of paths to work.

    Containers whose contained items are database backed (as opposed
    to singletons such as Root and ComputeList whose children are
    hardcoded) must override __getitem__, listnames and listcontent.

    """

    children = {}
    nicknames = []

    def __getitem__(self, key):
        """Returns the child item in this container with the given name."""
        return self.children.get(key)

    def listnames(self):
        """Lists the names of all items contained in this container."""
        return self.children.iterkeys()

    def listcontent(self):
        """Lists all the items contained in this container."""
        return self.children.itervalues()

    def to_dict(self):
        """Returns a dict representation of this model object."""
        if hasattr(self, '_storm_columns'):
            return dict((col.name, getattr(self, col.name)) for col in self._storm_columns.values())
        return {}

    def get_path(self):
        """Return the path to this object starting from the root as a list of object names."""
        return self.parent.get_path() + [self.name]

    def get_url(self):
        """Returns the canonical URL of this model object without the URI scheme and domain parts."""
        if not hasattr(self, 'parent'):
            raise Exception('Model object has no defined parent')
        return '%s%s/' % (self.parent.get_url(), self.name)


class SingletonModel(Model):
    """Base class for all models of which there should exist only a single instance."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SingletonModel, cls).__new__(cls, *args, **kwargs)
        return cls._instance


class Root(SingletonModel):
    """The root model.

    This model is the root of the object hierarchy.
    The parent object of this object is the object itself.

    Non-relative object traversals start from this object.

    """

    name = ''
    parent = property(lambda self: self)
    children = property(lambda self: {
        'compute': ComputeList(),
        'template': TemplateList(),
    })

    def __str__(self):
        return 'OMS root'

    def get_path(self):
        """Returns ['']."""
        return ['']

    def get_url(self):
        """Returns the string '/'."""
        return '/'


class TemplateList(SingletonModel):
    name = 'template'
    parent = property(lambda self: Root())

    def listcontent(self):
        return db.get_store().find(Template)

    def listnames(self):
        return (tpl.name for tpl in self.listcontent())

    def __getitem__(self, key):
        """Returns the Template instance with the ID specified by the given key."""
        try:
            id = int(key)
        except ValueError:
            return None
        else:
            return db.get_store().get(Template, id)

    def __str__(self):
        return 'Template list'


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


class ComputeList(SingletonModel):
    """Represents the container that contains all Compute instances stored in the database."""

    name = 'compute'
    parent = property(lambda self: Root())

    def listcontent(self):
        return db.get_store().find(Compute)

    def listnames(self):
        return (str(c.id) for c in self.listcontent())

    def __getitem__(self, key):
        """Returns the Compute instance with the ID specified by the given key."""
        try:
            id = int(key)
        except ValueError:
            return None
        else:
            return db.get_store().get(Compute, id)

    def __str__(self):
        return self.name


class Compute(Model):
    """Represents a compute."""

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

    @property
    def parent(self):
        """Returns the single ComputeList instance."""
        return ComputeList()

    @property
    def name(self):
        return str(self.id)

    @property
    def nicknames(self):
        """Returns all the nicknames of this Compute instance.

        Nicknames can be used to traverse to this object using
        alternative, potentially more convenient and/more memorable,
        names.

        """
        return [
            'c%s' % self.id,
            'compute%s' % self.id,
            self.hostname,
        ]

    def __str__(self):
        return 'compute%s' % (self.id, )


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



