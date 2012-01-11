from __future__ import absolute_import

from .root import OmsRoot
from .news import NewsItem

__all__ = [OmsRoot]

#__all__ = [OmsRoot, Machines, Computes, Compute, Templates, Template, Network, NetworkInterface, Storage, NewsItem, VncConsole, 'creatable_models']


#creatable_models = dict((cls.__name__.lower(), cls)
#                        for cls in [Compute, Template, Network, NetworkInterface, Storage, VirtualizationContainer, Hangar, NewsItem, VncConsole])

creatable_models = dict((cls.__name__.lower(), cls)
                        for cls in [NewsItem])
