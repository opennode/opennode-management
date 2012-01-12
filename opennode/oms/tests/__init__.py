from opennode.oms.zodb.db import init
from opennode.oms.core import setup_environ


def setup_package():
    init(test=True)
    setup_environ()

    # XXX: needed to run old unit tests that require the compute class which
    # has been moved to the Knot plugin
    from grokcore.component.testing import grok
    grok("opennode.oms.tests.test_compute")


def teardown_package():
    from opennode.oms.tests.util import teardown_reactor

    teardown_reactor()
