import persistent
from BTrees.IOBTree import IOBTree
from zope.interface import implements, Interface, Attribute
from zope.interface.interface import InterfaceClass


class IModel(Interface):
    __name__ = Attribute("Name")
    __parent__ = Attribute("Parent")


class IContainer(IModel):

    def __getitem__(key):
        """Returns the child item in this container with the given name."""

    def listnames():
        """Lists the names of all items contained in this container."""

    def listcontent():
        """Lists all the items contained in this container."""


class Model(persistent.Persistent):
    implements(IModel)

    __parent__ = None
    __name__ = None

    def to_dict(self):
        """Returns a dict representation of this model object."""
        raise NotImplementedError


class ReadonlyContainer(Model):
    """A container whose items cannot be modified, i.e. are predefined."""
    implements(IContainer)

    def __getitem__(self, key):
        return self._items.get(key)

    def listnames(self):
        return self._items.keys()

    def listcontent(self):
        return self._items.values()


class Container(ReadonlyContainer):
    """A base class for containers whose items are identified by
    sequential integer IDs.

    Does not support `__setitem__`; use `add(...)` instead.

    """

    __contains__ = Interface

    def __init__(self):
        self._items = IOBTree()

    def add(self, item):
        if isinstance(self.__contains__, InterfaceClass):
            if not self.__contains__.providedBy(item):
                raise Exception('Container can only contain items that provide %s' % self.__contains__.__name__)
        else:
            if not isinstance(item, self.__contains__):
                raise Exception('Container can only contain items that are instances of %s' % self.__contains__.__name__)

        if item.__parent__:
            if item.__parent__ is self:
                return
            item.__parent__.remove(item)
        item.__parent__ = self

        newid = self._items.maxKey() + 1 if self._items else 1
        self._items[newid] = item
        item.__name__ = str(newid)

    def remove(self, item):
        del self._items[item.__name__]

    def __delitem__(self, key):
        try:
            intkey = int(key)
        except ValueError:
            raise KeyError(key)
        else:
            del self._items[intkey]

    def __getitem__(self, key):
        """Returns the Template instance with the ID specified by the given key."""
        try:
            return self._items.get(int(key))
        except ValueError:
            return None


class OmsRoot(ReadonlyContainer):
    """The root of the OMS DB.

    This model is the root of the object hierarchy.

    Absolute object traversals start from this object.

    """

    __name__ = ''

    _items = property(lambda self: {
        'computes': self.computes,
        'templates': self.templates,
    })

    def __init__(self):
        self.computes = Computes()
        self.computes.__parent__ = self
        self.computes.__name__ = 'computes'

        self.templates = Templates()
        self.templates.__parent__ = self
        self.templates.__name__ = 'templates'

    def __str__(self):
        return 'OMS root'


class Template(Model):
    def __init__(self, name, base_type, min_cores, max_cores, min_memory, max_memory):
        self.name = name
        self.base_type = base_type
        self.min_cores = min_cores
        self.max_cores = max_cores
        self.min_memory = min_memory
        self.max_memory = max_memory
        self.computes = []


class Templates(Container):
    __contains__ = Template

    def __str__(self):
        return 'Template list'


class Compute(Model):

    def __init__(self, architecture, hostname, speed, memory, state, template=None):
        self.architecture = architecture
        self.hostname = hostname
        self.speed = speed
        self.memory = memory
        self.state = state
        self.template = template

    @property
    def nicknames(self):
        """Returns all the nicknames of this Compute instance.

        Nicknames can be used to traverse to this object using
        alternative, potentially more convenient and/more memorable,
        names.

        """
        return [
            'c%s' % self.__name__,
            'compute%s' % self.__name__,
            self.hostname,
        ]

    def __str__(self):
        return 'compute%s' % self.__name__


class Computes(Container):
    __contains__ = Compute

    def __str__(self):
        return 'Compute list'


class Network(Model):
    def __init__(self, vlan, label, state):
        self.vlan = vlan
        self.label = label
        self.state = state

        self.ipv4_address_range = None
        self.ipv4_gateway = None
        self.ipv6_address_range = None
        self.ipv6_gateway = None
        self.allocation = None
        self.devices = []


class NetworkDevice(Model):
    def __init__(self, interface, mac, state, network, compute):
        self.interface = interface
        self.mac = mac
        self.state = state
        self.network = network
        self.compute = compute


class Storage(Model):
    def __init__(self, size, state):
        self.size = size  # 1.1 GiB
        self.state = state  # online | offline | backup | snapshot | resize | degraded


class Tag(Model):
    def __init__(self, name):
        self.name = name
