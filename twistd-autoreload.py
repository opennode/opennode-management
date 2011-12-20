#!/usr/bin/env python
from twisted.scripts import twistd
from opennode.utils import autoreload
from twisted.internet import defer

defer.setDebugging(True)

autoreload.main(twistd.run)
