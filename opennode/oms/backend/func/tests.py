import unittest

from zope.interface import alsoProvides

from opennode.oms import discover_adapters
from opennode.oms.backend.operation import IFuncInstalled, IGetComputeInfo
from opennode.oms.model.model.compute import Compute
from .actions import FuncGetComputeInfo


def setUpModule():
    discover_adapters()


class FuncTestCase(unittest.TestCase):

    def testAdaption(self):
        compute = Compute(architecture='linux', hostname='tuxtest', speed=2000, memory=2048, state='online')
        alsoProvides(compute, IFuncInstalled)

        self.assertIsInstance(
            IGetComputeInfo(compute), FuncGetComputeInfo,
            "A Compute with IFuncInstalled should adapt to the appropriate Func action handler"
        )
