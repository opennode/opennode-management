from grokcore.component import context
from zope import schema
from zope.interface import Interface, implements

from opennode.oms.config import get_config
from opennode.oms.model.model import OmsRoot
from opennode.oms.model.model.base import ContainerInjector, Model, ReadonlyContainer


class IEtcConfig(Interface):
    pass


class IEtcConfigSection(Interface):
    """ Representation of a [section] within *.conf files """
    section = schema.TextLine(title=u"Section", min_length=1, readonly=True)
    settings = schema.Dict(title=u'Settings', key_type=schema.TextLine(), value_type=schema.TextLine(), readonly=True)


class EtcConfigSection(Model):
    implements(IEtcConfigSection)

    __transient__ = True

    def __init__(self, name, settings):
        self.__name__ = name
        self.settings = settings

    section = property(lambda self: self.__name__)


class EtcConfig(ReadonlyContainer):
    implements(IEtcConfig)

    __contains__ = IEtcConfigSection
    __name__ = 'etc'

    def listnames(self):
        return get_config().sections()

    def content(self):
        config = get_config()

        return {section: EtcConfigSection(section, dict(config.items(section))) for section in config.sections()}

    def __str__(self):
        return 'Configuration'


class EtcConfigRootInjector(ContainerInjector):
    context(OmsRoot)
    __class__ = EtcConfig
