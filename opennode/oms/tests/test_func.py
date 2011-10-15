import os
import unittest

from twisted.internet import defer
from zope.interface import alsoProvides

from opennode.oms.backend.operation import *
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


@unittest.skipUnless(funcd_running, "func not running")
@run_in_reactor(funcd_running and 4)
@defer.inlineCallbacks
def test_operate_vm():
    compute = Compute(architecture='linux', hostname='localhost', speed=2000, memory=2048, state='online')
    alsoProvides(compute, IFuncInstalled)

    backend = 'test://' + os.path.join(os.getcwd(), "opennode/oms/tests/u1.xml")

    job = IStartVM(compute)
    res = yield job.run(backend, 'vm1')
    assert res == None

    job = IShutdownVM(compute)
    res = yield job.run(backend, 'vm2')
    assert res == None

    job = IListVMS(compute)
    res = yield job.run(backend)
    assert res[1]['name'] == 'vm1'
    assert res[1]['state'] == 'inactive'
