from __future__ import absolute_import

from zope import schema
from zope.interface import Interface, implements

from .base import Model, Container
from .compute import VirtualCompute, IInPhysicalCompute


class IVirtualizationContainer(Interface):
    backend = schema.Choice(title=u"Backend", values=(u'xen', u'kvm'))


class VirtualizationContainer(Container):
    implements(IVirtualizationContainer, IInPhysicalCompute)

    __contains__ = VirtualCompute

    def __init__(self, backend):
        super(VirtualizationContainer, self).__init__()

        self.backend = backend

        self.__name__ = 'vms'

    def __str__(self):
        return 'virtualizationcontainer%s' % self.__name__
