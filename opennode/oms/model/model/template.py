from __future__ import absolute_import

from zope import schema
from zope.component import provideSubscriptionAdapter
from zope.interface import Interface, implements

from .base import Model, Container
from .byname import ByNameContainerExtension


class ITemplate(Interface):
    name = schema.TextLine(title=u"Template name", min_length=2)
    base_type = schema.Choice(title=u"Template type", values=(u'xen', u'kvm'))
    min_cores = schema.Int(title=u"Min cores", description=u"Minimum number of cores", required=False)
    max_cores = schema.Int(title=u"Max cores", description=u"Maximum number of cores", required=False)
    min_memory = schema.Int(title=u"Min memory", description=u"Minimum amount of memory", required=False)
    max_memory = schema.Int(title=u"Max memory", description=u"Maximum amount of memory", required=False)


class Template(Model):
    implements(ITemplate)

    def __init__(self, name, base_type, min_cores=0, max_cores=float('inf'), min_memory=0, max_memory=float('inf')):
        self.name = name
        self.base_type = base_type
        self.min_cores = min_cores
        self.max_cores = max_cores
        self.min_memory = min_memory
        self.max_memory = max_memory
        self.computes = []

    def display_name(self):
        return self.name


class Templates(Container):
    __contains__ = Template

    def __str__(self):
        return 'Template list'

provideSubscriptionAdapter(ByNameContainerExtension, adapts=(Templates, ))
