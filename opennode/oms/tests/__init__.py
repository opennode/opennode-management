from opennode.oms.zodb.db import init
from opennode.oms import setup_environ


def setup_package():
    setup_environ()
    init(test=True)
