from __future__ import absolute_import

from zope import schema
from zope.interface import Interface, implements

from .base import ReadonlyContainer, Container, Model
from .symlink import Symlink


class INetworkInterface(Interface):
    name = schema.TextLine(title=u"Interface name", min_length=3)
    hw_address = schema.TextLine(title=u"MAC", min_length=17)
    state = schema.Choice(title=u"State", values=(u'active', u'inactive'))
    ipv4_address = schema.TextLine(title=u"IPv4 network address", min_length=7, required=False)
    ipv6_address = schema.TextLine(title=u"IPv6 network address", min_length=7, required=False)

    metric = schema.Int(title=u"Metric")
    bcast = schema.TextLine(title=u"Broadcast")
    stp = schema.Bool(title=u"STP enabled")
    rx = schema.TextLine(title=u"RX bytes")
    tx = schema.TextLine(title=u"TX bytes")


class IBridgeInterface(INetworkInterface):
    members = schema.List(title=u"Bridge members", required=False, readonly=True)


class NetworkInterface(ReadonlyContainer):
    implements(INetworkInterface)

    def __init__(self, name, network, hw_address, state):
        self.__name__ = name
        self.name = name
        self.hw_address = hw_address
        self.state = state
        self.network = network

        self.metric = 1
        self.tx = ''
        self.rx = ''
        self.stp = False

        self.ipv6_address = ''
        self.ipv4_address = ''

    @property
    def _items(self):
        if self.network:
            return {'network': Symlink('network', self.network)}
        return {}

    @property
    def bcast(self):
        if not self.ipv4_address:
            return None

        ip, prefix = self.ipv4_address.split('/')
        l = 0
        for b in ip.split('.'):
            l = l << 8 | int(b)
        mask = 0xffffffff
        for i in xrange(0, int(prefix)):
            mask = mask >> 1
        l = l | mask
        o = []
        for i in xrange(0, 4):
            o.insert(0, l & 0xff)
            l = l >> 8
        return '.'.join(str(i) for i in o)


class BridgeInterface(NetworkInterface):
    implements(IBridgeInterface)

    def __init__(self, *args):
        super(BridgeInterface, self).__init__(*args)

        self.members = []

    @property
    def _items(self):
        res = super(BridgeInterface, self)._items
        # TODO: add symlinks for bridge members
        return res


class NetworkInterfaces(Container):
    __contains__ = INetworkInterface

    __name__ = 'interfaces'


class INetworkRoute(Interface):
    destination = schema.TextLine(title=u"Destination", min_length=7, required=True)
    gateway = schema.TextLine(title=u"Gateway", min_length=7, required=True)
    flags = schema.TextLine(title=u"Flags", required=True)
    metrics = schema.Int(title=u"Metrics", required=True)


class NetworkRoute(Container):
    implements(INetworkRoute)

    @property
    def nicknames(self):
        return [self.destination, self.gateway, self.flags, str(self.metrics)]


class NetworkRoutes(Container):
    __contains__ = INetworkRoute

    __name__ = 'routes'


class INetwork(Interface):
    state = schema.Choice(title=u"State", values=(u'active', u'inactive'))
    ipv4_address = schema.TextLine(title=u"IPv4 network address", min_length=7)
    ipv4_gateway = schema.TextLine(title=u"IPv4 Gateway", min_length=7)
    ipv4_address_range = schema.TextLine(title=u"IPv4 Range", min_length=7, required=False)
    ipv6_address = schema.TextLine(title=u"IPv6 network address", min_length=7, required=False)
    ipv6_gateway = schema.TextLine(title=u"IPv6 Gateway", min_length=6, required=False)
    ipv6_address_range = schema.TextLine(title=u"IPv6 Range", min_length=7, required=False)

    vlan = schema.TextLine(title=u"VLan", required=False)
    label = schema.TextLine(title=u"Label", required=False)


class Network(Model):
    implements(INetwork)

    def __init__(self, state):
        self.state = state

        self.vlan = None
        self.label = None

        self.ipv4_address = None
        self.ipv4_gateway = None
        self.ipv4_address_range = None
        self.ipv6_address = None
        self.ipv6_gateway = None
        self.ipv6_address_range = None

        self.allocation = None
        self.devices = []


class Networks(Container):
    __contains__ = INetwork

    __name__ = 'networks'
