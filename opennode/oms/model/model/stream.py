from __future__ import absolute_import

from grokcore.component import Subscription, baseclass
from zope.component import queryAdapter
from zope.interface import implements

from .base import ReadonlyContainer, Model, IModel, IContainerExtender
from zope.keyreference.persistent import KeyReferenceToPersistent
from collections import defaultdict


class IStream(IModel):
    def events(after, limit):
        pass

    def add(event):
        pass


class IMetrics(IModel):
    pass


class TransientStream(Model):
    """A stream which stores the data in memory in a capped collection"""

    implements(IStream)

    MAX_LEN = 100

    # Since this class is designed to be not persistent nor unique during
    # execution, but reinstantiated at each traversal, we have to keepp
    # the actual data somewhere. A two level dictionary structure serves the purpose
    # key (parent model + metric name)
    transient_store = defaultdict(lambda: defaultdict(list))

    def __init__(self, parent, name):
        self.__parent__ = parent
        self.__name__ = name

    @property
    def data(self):
        return self.transient_store[KeyReferenceToPersistent(self.__parent__.__parent__)][self.__name__]

    def events(self, after, limit = None):
        res = []
        for idx, (ts, value) in enumerate(self.data):
            if ts <= after or (limit and idx >= limit):
                break
            res.append((ts, value))

        return res

    def add(self, event):
        self.data.insert(0, event)

        if len(self.data) > self.MAX_LEN:
            self.data.pop()


class StreamSubscriber(ReadonlyContainer):
    __name__ = 'stream'

    _items = {}


class Metrics(ReadonlyContainer):
    implements(IMetrics)

    __name__ = 'metrics'

    def __init__(self, parent):
        self.__parent__ = parent

    @property
    def _items(self):
        metrics = queryAdapter(self.__parent__, IMetrics)
        return dict((i, TransientStream(self, i)) for i in metrics)


class MetricsContainerExtension(Subscription):
    implements(IContainerExtender)
    baseclass()

    def extend(self):
        return {'metrics': Metrics(self.context)}
