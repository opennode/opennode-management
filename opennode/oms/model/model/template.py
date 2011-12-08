from __future__ import absolute_import

from grokcore.component import context
from zope import schema
from zope.component import provideSubscriptionAdapter
from zope.interface import Interface, implements

from .base import Model, Container, IDisplayName
from .byname import ByNameContainerExtension
from .search import ModelTags


class ITemplate(Interface):
    name = schema.TextLine(title=u"Template name", min_length=2)
    base_type = schema.Choice(title=u"Template type", values=(u'xen', u'kvm', u'openvz'))
    
    cores = schema.Tuple(
        title=u"Number of virtual cores", description=u"Minimal, suggested and maximal number of cores",
        value_type=schema.Int(),
        required=False)
    memory = schema.Tuple(
        title=u"Memory size", description=u"Minimal, suggested and maximal memory size (in GB)",
        value_type=schema.Float(),
        required=False)
    swap = schema.Tuple(
        title=u"Memory size", description=u"Minimal, suggested and maximal memory size (in GB)",
        value_type=schema.Float(),
        required=False)
    disk = schema.Tuple(
        title=u"Disk size", description=u"Minimal, suggested and maximal disk size",
        value_type=schema.Float(),
        required=False)
    cpu_limit = schema.Tuple(
        title=u"CPU usage limits", description=u"Minimal, suggested and maximal cpu_limit",
        value_type=schema.Int(),
        required=False)
    
    password = schema.TextLine(title=u"Default password", required=False)
    ip = schema.TextLine(title=u"Default password", required=False)
    nameserver = schema.TextLine(title=u"Default password", required=False)
    
class Template(Model):
    implements(ITemplate, IDisplayName)

    def __init__(self, name, base_type):
        self.name = name
        self.base_type = base_type

    def display_name(self):
        return self.name

    @property
    def nicknames(self):
        return [self.name, self.base_type]


class TemplateTags(ModelTags):
    context(Template)

    def auto_tags(self):
        return [u'virt_type:' + self.context.base_type]


class Templates(Container):
    __contains__ = Template

    def __str__(self):
        return 'Template list'

provideSubscriptionAdapter(ByNameContainerExtension, adapts=(Templates, ))
