from zope.interface import Interface


__all__ = ['IJob', 'IFuncInstalled', 'IGetComputeInfo', 'IListVMS', 'IStartVM', 'IShutdownVM', 'IDestroyVM']


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

class IListVMS(IJob):
    """List vms"""

class IStartVM(IJob):
    """Starts a vm."""

class IShutdownVM(IJob):
    """Shuts down a vm."""

class IDestroyVM(IJob):
    """Destroys a vm."""
