from __future__ import absolute_import

from zope import schema
from zope.interface import Interface, implements

from .base import Model, Container
from .compute import Compute, IInCompute


class IVirtualizationContainer(Interface):
    backend = schema.Choice(title=u"Backend", values=(u'xen', u'kvm', u'openvz', u'lxc'))


class VirtualizationContainer(Container):
    implements(IVirtualizationContainer, IInCompute)

    __contains__ = Compute

    def __init__(self, backend):
        super(VirtualizationContainer, self).__init__()

        self.backend = backend

        self.__name__ = 'vms'

    def __str__(self):
        return 'virtualizationcontainer%s' % self.__name__
