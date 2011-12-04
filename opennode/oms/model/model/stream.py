from __future__ import absolute_import

from grokcore.component import Subscription, baseclass
from zope.component import queryAdapter
from zope.interface import implements

from .base import ReadonlyContainer, Model, IModel, IContainerExtender
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
    transient_store = defaultdict(list)

    def __init__(self, parent, name):
        self.__parent__ = parent
        self.__name__ = name

    @property
    def data(self):
        from opennode.oms.model.traversal import canonical_path
        return self.transient_store[canonical_path(self)]

    def events(self, after, limit = None):
        # XXX: if nobody fills the data (func issues) then we return fake data
        if not self.data:
            return self._fake_events(after, limit)

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

    def _fake_events(self, after, limit = None):
        import random, time
        timestamp = int(time.time() * 1000)

        def fake_data():
            r = self.__name__
            if r.endswith('cpu_usage'):
                return random.random()
            if r.endswith('memory_usage'):
                return random.randint(0, 100)
            if r.endswith('network_usage'):
                return random.randint(0, 100)
            if r.endswith('diskspace_usage'):
                return random.random() * 0.5 + 600  # useful

        return [[timestamp, fake_data()]]


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
