#!/usr/bin/env python
from twisted.scripts import twistd
from pyutils import autoreload

autoreload.main(twistd.run)
