from __future__ import absolute_import

from zope import schema
from zope.component import provideSubscriptionAdapter
from zope.interface import Interface, implements

from .actions import ActionsContainerExtension
from .base import Container
from .byname import ByNameContainerExtension
from .compute import Compute, IInCompute
from .search import ITagged


class IVirtualizationContainer(Interface):
    backend = schema.Choice(title=u"Backend", values=(u'xen', u'kvm', u'openvz', u'lxc'))


class VirtualizationContainer(Container):
    implements(IVirtualizationContainer, IInCompute, ITagged)

    __contains__ = Compute

    def __init__(self, backend):
        super(VirtualizationContainer, self).__init__()

        self.backend = backend

        self.__name__ = 'vms'

    def __str__(self):
        return 'virtualizationcontainer%s' % self.__name__

    def tags(self):
        return [self.backend.encode('utf-8')]


provideSubscriptionAdapter(ActionsContainerExtension, adapts=(VirtualizationContainer, ))
provideSubscriptionAdapter(ByNameContainerExtension, adapts=(VirtualizationContainer, ))
