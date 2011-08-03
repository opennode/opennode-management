from __future__ import absolute_import

from .base import Model


class NetworkDevice(Model):
    def __init__(self, interface, mac, state, network, compute):
        self.interface = interface
        self.mac = mac
        self.state = state
        self.network = network
        self.compute = compute


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
