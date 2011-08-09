from zope.interface import alsoProvides

from opennode.oms.backend.operation import IFuncInstalled, IGetComputeInfo
from opennode.oms.model.model.compute import Compute
from opennode.oms.backend.func.actions import FuncGetComputeInfo


def test_adaption():
    compute = Compute(architecture='linux', hostname='tuxtest', speed=2000, memory=2048, state='online')
    alsoProvides(compute, IFuncInstalled)
    assert isinstance(IGetComputeInfo(compute, None), FuncGetComputeInfo)
