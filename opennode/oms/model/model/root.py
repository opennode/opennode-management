from __future__ import absolute_import

from BTrees.OOBTree import OOBTree
from grokcore.component import Subscription, context, implements

from .base import ReadonlyContainer, IContainerInjector, IContainerExtender

from .bin import Bin
from .log import Log
from .proc import Proc
from .search import SearchContainer
from .stream import StreamSubscriber
from .plugins import Plugins


class OmsRoot(ReadonlyContainer):
    """The root of the OMS DB.

    This model is the root of the object hierarchy.

    Absolute object traversals start from this object.

    """

    __name__ = ''

    # Always inherits the global permissions
    inherit_permissions = True

    def __init__(self):
        self._items = OOBTree()

    def __str__(self):
        return 'OMS root'


class RootContainerInjector(Subscription):
    implements(IContainerInjector)
    context(OmsRoot)

    def inject(self):
        return {'log': Log(),
                'search': SearchContainer(),
                }


class RootContainerExtension(Subscription):
    implements(IContainerExtender)
    context(OmsRoot)

    def extend(self):
        # XXX: This is not really DRY: which one should be shown 'bin', or Bin.__name__?
        return {'bin': Bin(),
                'proc': Proc(),
                'plugins': Plugins(),
                'stream': StreamSubscriber(),
                }
