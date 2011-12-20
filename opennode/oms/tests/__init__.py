from opennode.oms.zodb.db import init
from opennode.oms.core import setup_environ
from opennode.oms.tests.util import teardown_reactor


def setup_package():
    setup_environ()
    init(test=True)


def teardown_package():
    teardown_reactor()
