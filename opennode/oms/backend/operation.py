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


class IHostInterfaces(IJob):
    """Returns detailed info about host interfaces. hardware.info doesn't work on all archs."""


class IGetGuestMetrics(IJob):
    """Returns guest VM metrics."""


class IGetLocalTemplates(IJob):
    """Get local templates"""


class IDeployVM(IJob):
    """Deploys a vm."""


class IUndeployVM(IJob):
    """Undeploys a vm."""


class IListVMS(IJob):
    """List vms"""


class IStartVM(IJob):
    """Starts a vm."""


class IShutdownVM(IJob):
    """Shuts down a vm."""


class IDestroyVM(IJob):
    """Destroys a vm."""


class ISuspendVM(IJob):
    """Suspends a vm."""


class IResumeVM(IJob):
    """Resumes a vm."""


class IRebootVM(IJob):
    """Reboots a vm."""
