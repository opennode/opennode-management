import unittest

from opennode.oms.db import DB_URI
from storm.database import create_database
from storm.store import Store
from opennode.oms.model.model import Compute, Network, NetworkDevice

class Test(unittest.TestCase):


    def setUp(self):
        self.db = create_database(DB_URI)
        self.s = Store(self.db)

    def tearDown(self):
        self.s.rollback()
        self.s.close()


    def testSimpleCreation(self):
        c = Compute()
        c.hostname = u'test.host'
        self.s.add(c)

        n = Network()
        n.ipv4_address_range = u'192.168.1.0/24'
        self.s.add(n)

        nd = NetworkDevice()
        nd.mac = u'aa:bb:cc:dd:ee:ee'
        nd.compute = c
        nd.network = n
        self.s.add(nd)

        nd = NetworkDevice()
        nd.mac = u'aa:bb:cc:dd:ee:ff'
        nd.network = n
        self.s.add(nd)

        self.s.flush()
        self.assertEquals(c.network_devices.count(), 1)
        self.assertEquals(n.devices.count(), 2)


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
