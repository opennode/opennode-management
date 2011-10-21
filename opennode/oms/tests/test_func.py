import unittest

from zope.interface import alsoProvides

from opennode.oms.backend.operation import IFuncInstalled, IGetComputeInfo
from opennode.oms.model.model.compute import Compute
from opennode.oms.backend.func import FuncGetComputeInfo
from opennode.oms.tests.util import run_in_reactor, funcd_running


def test_adaption():
    compute = Compute(architecture='linux', hostname='tuxtest', memory=2048, state='online')
    alsoProvides(compute, IFuncInstalled)
    assert isinstance(IGetComputeInfo(compute, None), FuncGetComputeInfo)


@unittest.skipUnless(funcd_running, "func not running")
@run_in_reactor(funcd_running and 2)
def test_get_info():
    compute = Compute(architecture='linux', hostname='localhost', memory=2048, state='online')
    alsoProvides(compute, IFuncInstalled)
    job = IGetComputeInfo(compute, None)
    job.run()
