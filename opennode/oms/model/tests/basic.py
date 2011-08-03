import unittest

from storm.database import create_database
from storm.store import Store

from opennode.oms.db.db import DB_URI
from opennode.oms.model.model import compute, network


class Test(unittest.TestCase):

    def setUp(self):
        db = create_database(DB_URI)
        self.store = Store(db)

    def tearDown(self):
        self.store.rollback()
        self.store.close()

    def testSimpleCreation(self):
        compute = compute.Compute()
        compute.hostname = u'test.host'
        self.store.add(compute)

        network = network.Network()
        network.ipv4_address_range = u'192.168.1.0/24'
        self.store.add(network)

        network_device = network.NetworkDevice()
        network_device.mac = u'aa:bb:cc:dd:ee:ee'
        network_device.compute = compute
        network_device.network = network
        self.store.add(network_device)

        network_device = network.NetworkDevice()
        network_device.mac = u'aa:bb:cc:dd:ee:ff'
        network_device.network = network
        self.store.add(network_device)

        self.store.flush()
        self.assertEquals(compute.network_devices.count(), 1)
        self.assertEquals(network.devices.count(), 2)


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
