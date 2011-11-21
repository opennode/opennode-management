import os
import shutil
import time
import unittest
from xml.etree import ElementTree

from twisted.internet import defer
from zope.interface import alsoProvides

from opennode.oms.backend.func import FuncGetComputeInfo
from opennode.oms.backend.operation import IFuncInstalled, IGetComputeInfo, IStartVM, IShutdownVM, IListVMS
from opennode.oms.model.form import ApplyRawData
from opennode.oms.model.model.compute import Compute
from opennode.oms.model.model.virtualizationcontainer import VirtualizationContainer
from opennode.oms.tests.util import run_in_reactor, funcd_running


def make_compute(hostname=u'tux-for-test', state=u'active', memory=2000):
    return Compute(hostname, state, memory)


def test_adaption():
    compute = make_compute()
    alsoProvides(compute, IFuncInstalled)
    assert isinstance(IGetComputeInfo(compute, None), FuncGetComputeInfo)


@unittest.skipUnless(funcd_running, "func not running")
@run_in_reactor(funcd_running and 2)
def test_get_info():
    compute = make_compute(hostname=u'localhost')
    alsoProvides(compute, IFuncInstalled)
    job = IGetComputeInfo(compute, None)
    job.run()


@unittest.skipUnless(funcd_running, "func not running")
@run_in_reactor(funcd_running and 1)
@defer.inlineCallbacks
def test_operate_vm():
    compute = make_compute(hostname=u'localhost')
    alsoProvides(compute, IFuncInstalled)

    backend = 'test://' + os.path.join(os.getcwd(), "opennode/oms/tests/u1.xml")

    job = IStartVM(compute)
    res = yield job.run(backend, '4dea22b31d52d8f32516782e98ab3fa0')
    assert res == None

    job = IShutdownVM(compute)
    res = yield job.run(backend, 'EF86180145B911CB88E3AFBFE5370493')
    assert res == None

    job = IListVMS(compute)
    res = yield job.run(backend)
    assert res[1]['name'] == 'vm1'
    assert res[1]['state'] == 'inactive'


@unittest.skipUnless(funcd_running, "func not running")
@run_in_reactor(funcd_running and 2)
def test_activate_compute():
    shutil.copy(os.path.join(os.getcwd(), 'opennode/oms/tests/u1.xml'), '/tmp/func_vm_test_state.xml')

    compute = make_compute(hostname=u'vm1', state=u'inactive')
    compute.__name__ = '4dea22b31d52d8f32516782e98ab3fa0'

    dom0 = make_compute(hostname=u'localhost', state=u'active')
    alsoProvides(dom0, IFuncInstalled)

    container = VirtualizationContainer('test')
    container.__parent__ = dom0
    compute.__parent__ = container

    assert compute.effective_state == 'inactive'

    a = ApplyRawData({'state': 'active'}, compute)
    a.apply()

    time.sleep(0.5)

    assert compute.effective_state == 'active'

    root = ElementTree.parse('/tmp/func_vm_test_state.xml')
    for node in root.findall('domain'):
        if node.find('name').text == 'vm1':
            assert node.attrib['state'] == 'active'
            return

    assert False
