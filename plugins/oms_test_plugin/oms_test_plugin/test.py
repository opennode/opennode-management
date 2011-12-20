from __future__ import absolute_import

from grokcore.component import context, name, implements
from zope import schema
from zope.interface import Interface

from opennode.oms.endpoint.httprest.base import HttpRestView
from opennode.oms.model.model.plugins import IPlugin, PluginInfo


class ICustomInfoPlugin(Interface):
    custom_attribute = schema.TextLine(title=u"Custom plugin metadata")


class CustomInfoPlugin(PluginInfo):
    implements(IPlugin, ICustomInfoPlugin)

    def __init__(self, *args):
        super(CustomInfoPlugin, self).__init__(*args)

        self.custom_attribute = 'test'

    def initialize(self):
        print "[CustomInfoPlugin] initializing plugin"


class TestRestView(HttpRestView):
    context(CustomInfoPlugin)
    name('root')

    def render(self, request):
        return "some custom plugin response"
