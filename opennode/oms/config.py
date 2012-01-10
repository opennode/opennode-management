import os

from ConfigParser import ConfigParser, Error as ConfigKeyError
from grokcore.component import Subscription, implements, context, querySubscriptions
from grokcore.component.testing import grok
from zope.interface import Interface

import opennode.oms

_config = None
_loaded_config_requirements = []


def get_config():
    global _config
    if not _config:
        # ensure that our config file subscription adapter has been grokked
        # this is tricky because we need a configuration object at the very beginning of 
        # the startup sequence
        if not querySubscriptions(object(), IRequiredConfigurationFiles):
            grok('opennode.oms.config')

        _config = OmsConfig()
    return _config


def update():
    """Update a config file reload"""
    _config.update()


class IRequiredConfigurationFiles(Interface):
    def config_file_names():
        """Used by plugins to define which are the required configuration files"""


class OMSRequiredConfigurationFiles(Subscription):
    implements(IRequiredConfigurationFiles)
    context(object)

    def config_file_names(self):
        return gen_config_file_names(opennode.oms, 'oms')


def gen_config_file_names(module, name):
    """Generate a list of standard configuration files for a given software package:
    defaults contained in egg, configuration file in current directory (usually installation dir), and user override"""

    base_dir = os.path.dirname(os.path.dirname(module.__path__[0]))
    return [i % name for i in ['%s/opennode-%%s.conf' % base_dir, './opennode-%s.conf', '/etc/opennode/opennode-%s.conf']]


class OmsConfig(ConfigParser):
    __default_files__ = object()

    def __init__(self, config_filenames=__default_files__):
        ConfigParser.__init__(self)
        self.update(config_filenames)

    def update(self, config_filenames=__default_files__):
        if config_filenames == self.__default_files__:
            conf_requirements = [i for i in querySubscriptions(object(), IRequiredConfigurationFiles) if type(i) not in _loaded_config_requirements]

            config_filenames = []
            for i in [i.config_file_names() for i in conf_requirements]:
                config_filenames.extend(i)

            for i in conf_requirements:
                _loaded_config_requirements.append(type(i))

            # user override must be last
            config_filenames.append('~/.opennode-oms.conf')

        print "Reading config files", ', '.join(config_filenames)
        self.read([os.path.expanduser(i) for i in config_filenames])

    def getboolean(self, section, option, default=False):
        try:
            return ConfigParser.getboolean(self, section, option)
        except ConfigKeyError:
            return default

    def getint(self, section, option, default=False):
        try:
            return ConfigParser.getint(self, section, option)
        except ConfigKeyError:
            return default

    def getfloat(self, section, option, default=False):
        try:
            return ConfigParser.getfloat(self, section, option)
        except ConfigKeyError:
            return default
