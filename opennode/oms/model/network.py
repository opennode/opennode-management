
class Network():
    id = None
    vlan = None
    label = None
    state = None

    # ip-network
    ipv4_address_range = None
    ipv4_gateway = None
    ipv6_address_range = None
    ipv6_gateway = None
    allocation = None # dynamic | static

def NetworkDevice():
    network_id = None
    interface = None
    mac = None
    state = None # active | inactive
