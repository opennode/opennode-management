from grokcore.component import implements

from opennode.oms.model.model.plugins import IPlugin


class SimpleTestPlugin(object):
    implements(IPlugin)

    def initialize(self):
        print "[SimpleTestPlugin] initializing plugin"
