from __future__ import absolute_import

import pkg_resources
import sys

from grokcore.component import subscribe
from pkg_resources import working_set
from zope import schema
from zope.interface import Interface, implements

from .base import ReadonlyContainer, Model
from opennode.oms import config
from opennode.oms.util import Singleton
from opennode.oms.core import IApplicationInitializedEvent


class IPluginInfo(Interface):
    name = schema.TextLine(title=u"Plugin name")


class IPlugin(Interface):
    def initialize():
        """Called when the plugin is initialized"""


class PluginInfo(Model):
    implements(IPluginInfo)

    def __init__(self, parent, name):
        self.__parent__ = parent
        self.__name__ = name


class Plugins(ReadonlyContainer):
    __metaclass__ = Singleton
    __name__ = 'plugins'

    ENTRY_POINT_NAME = 'oms.plugins'

    def __init__(self):
        self._items = {}

    def load_eggs(self, search_path, auto_enable=None):
        # Note that the following doesn't seem to support unicode search_path
        distributions, errors = working_set.find_plugins(
            pkg_resources.Environment(search_path)
        )
        for dist in distributions:
            if dist not in working_set:
                working_set.add(dist)

        def _log_error(item, e):
            print "[plugins] error loading", item, e

        for dist, e in errors.iteritems():
            # ignore version conflict of modules which are not OMS plugins
            if self.ENTRY_POINT_NAME in dist.get_entry_map():
                _log_error(dist, e)

        for entry in sorted(working_set.iter_entry_points(self.ENTRY_POINT_NAME),
                            key=lambda entry: entry.name):

            # print '[plugins] Loading %s from %s' % (entry.name, entry.dist.location)
            try:
                entry.load(require=True)
            except Exception, e:
                _log_error(entry, e)
            else:
                yield entry

    def load_plugin(self, entry):
        from grokcore.component.testing import grok

        grok(entry.module_name)

        plugin_class = entry.load()
        if IPluginInfo.implementedBy(plugin_class):
            plugin = plugin_class(self, entry.name)
        else:
            plugin = plugin_class()

        if IPlugin.implementedBy(plugin_class):
            plugin.initialize()

        return plugin

    def load_plugins(self):
        for entrypoint in self.load_eggs(sys.path):
            plugin = self.load_plugin(entrypoint)
            self._items[entrypoint.name] = plugin if IPluginInfo.providedBy(plugin) else PluginInfo(self, entrypoint.name)

        config.update()


@subscribe(IApplicationInitializedEvent)
def load_plugins(event):
    Plugins().load_plugins()
