from zope.interface import Interface


class IJob(Interface):

    def run():
        pass

    def start_polling():
        pass


class IFuncInstalled(Interface):
    """Marker for FUNC-controlled Computes."""


class IBotoManageable(Interface):
    """Marker for Computes controlled through the boto library."""


class IGetComputeInfo(IJob):
    """Returns general information about a compute (os, architecture, devices, etc)."""
