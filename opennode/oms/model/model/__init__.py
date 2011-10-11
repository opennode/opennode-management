from __future__ import absolute_import

from .compute import Computes, Compute
from .machines import Machines
from .virtualizationcontainer import VirtualizationContainer
from .hangar import Hangar
from .network import Network, NetworkDevice
from .root import OmsRoot
from .storage import Storage
from .template import Templates, Template


__all__ = [OmsRoot, Machines, Computes, Compute, Templates, Template, Network, NetworkDevice, Storage, 'creatable_models']


creatable_models = dict((cls.__name__.lower(), cls)
                        for cls in [Compute, Template, Network, NetworkDevice, Storage, VirtualizationContainer, Hangar])
