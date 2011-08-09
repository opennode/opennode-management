from zope.interface import alsoProvides

from opennode.oms import discover_adapters
from opennode.oms.backend.operation import IFuncInstalled, IGetComputeInfo
from opennode.oms.model.model.compute import Compute
from .actions import FuncGetComputeInfo


def setUpModule():
    discover_adapters()


def test_adaption():
    compute = Compute(architecture='linux', hostname='tuxtest', speed=2000, memory=2048, state='online')
    alsoProvides(compute, IFuncInstalled)
    assert isinstance(IGetComputeInfo(compute), FuncGetComputeInfo)
