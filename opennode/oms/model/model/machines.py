from __future__ import absolute_import

from zope.component import provideSubscriptionAdapter

from .base import Container
from .compute import Compute
from .hangar import Hangar
from .byname import ByNameContainerExtension


class Machines(Container):
    __contains__ = Compute

    def __init__(self):
        super(Machines, self).__init__()
        self.hangar = Hangar()
        self._add(self.hangar)

    def __str__(self):
        return 'Machines list'


provideSubscriptionAdapter(ByNameContainerExtension, adapts=(Machines, ))
