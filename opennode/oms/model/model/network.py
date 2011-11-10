from __future__ import absolute_import

from zope import schema
from zope.interface import Interface, implements

from .base import ReadonlyContainer, Container, Model
from .symlink import Symlink


class INetworkInterface(Interface):
    name = schema.TextLine(title=u"Interface name", min_length=3)
    mac = schema.TextLine(title=u"MAC", min_length=17)
    state = schema.Choice(title=u"State", values=(u'active', u'inactive'))
    ipv4_address = schema.TextLine(title=u"IPv4 network address", min_length=7, required=False)


class IBridgeInterface(INetworkInterface):
    members = schema.List(title=u"Bridge members", required=False, readonly=True)


class NetworkInterface(ReadonlyContainer):
    implements(INetworkInterface)

    def __init__(self, name, network, mac, state):
        self.__name__ = name
        self.name = name
        self.mac = mac
        self.state = state
        self.network = network

    @property
    def _items(self):
        if self.network:
            return {'network': Symlink('network', self.network)}
        return {}


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
