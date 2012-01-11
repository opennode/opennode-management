from opennode.oms.zodb.db import init
from opennode.oms.core import setup_environ
from opennode.oms.tests.util import teardown_reactor


def setup_package():
    init(test=True)
    setup_environ()


def teardown_package():
    teardown_reactor()
