from __future__ import absolute_import

from .compute import Computes, Compute
from .hangar import Hangar
from .machines import Machines
from .network import Network, NetworkDevice
from .news import NewsItem
from .root import OmsRoot
from .storage import Storage
from .template import Templates, Template
from .virtualizationcontainer import VirtualizationContainer


__all__ = [OmsRoot, Machines, Computes, Compute, Templates, Template, Network, NetworkDevice, Storage, NewsItem,  'creatable_models']


creatable_models = dict((cls.__name__.lower(), cls)
                        for cls in [Compute, Template, Network, NetworkDevice, Storage, VirtualizationContainer, Hangar, NewsItem])
