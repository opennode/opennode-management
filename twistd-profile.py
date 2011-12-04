#!/usr/bin/env python
from twisted.scripts import twistd
from twisted.internet import defer
import cProfile

defer.setDebugging(True)

cProfile.run('twistd.run()', 'omsprof')
