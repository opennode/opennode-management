from zope.interface import Interface
from grokcore.component import context, Adapter, implements

class IJob(Interface):
    def run():
        pass

    def start_polling():
        pass


class IFuncInstalled(Interface):
    """Marker for for FUNC-controlled Computes."""


class IBotoManageable(Interface):
    """Marker for machines controlled through boto library."""


class IGetComputeInfo(IJob):
    """Returns general information about a host (os, architecture, devices, etc)."""

