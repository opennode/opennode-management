from __future__ import absolute_import

import time

from grokcore.component import Subscription, baseclass, Adapter, context, subscribe
from zope.component import queryAdapter
from zope.interface import implements

from .base import ReadonlyContainer, Model, IModel, IContainerExtender
from opennode.oms.config import get_config
from opennode.oms.model.model.events import IModelModifiedEvent, IModelDeletedEvent, IModelCreatedEvent
from collections import defaultdict


class IStream(IModel):
    def events(after, limit):
        pass

    def add(event):
        pass


class IMetrics(IModel):
    pass


class TransientStreamModel(Model):
    """A model which represents a a transient stream"""

    def __init__(self, parent, name):
        self.__parent__ = parent
        self.__name__ = name


class TransientStream(Adapter):
    """A stream which stores the data in memory in a capped collection"""

    implements(IStream)
    baseclass()

    MAX_LEN = 100

    # Since this class is designed to be not persistent nor unique during
    # execution, but reinstantiated at each traversal, we have to keepp
    # the actual data somewhere. A two level dictionary structure serves the purpose
    # key (parent model + metric name)
    transient_store = defaultdict(list)

    @property
    def data(self):
        from opennode.oms.model.traversal import canonical_path
        path = canonical_path(self.context)
        return self.transient_store[path]

    def events(self, after, limit=None):
        # XXX: if nobody fills the data (func issues) then we return fake data
        if not self.data and get_config().getboolean('metrics', 'fake_metrics', False):
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

    def _fake_events(self, after, limit=None):
        import random
        timestamp = int(time.time() * 1000)

        def fake_data():
            from opennode.oms.model.traversal import canonical_path
            r = canonical_path(self.context)
            if r.endswith('cpu_usage'):
                return random.random()
            elif r.endswith('memory_usage'):
                return random.randint(0, 100)
            elif r.endswith('network_usage'):
                return random.randint(0, 100)
            elif r.endswith('diskspace_usage'):
                return random.random() * 0.5 + 600  # useful
            else:
                raise Exception('cannot fake')

        try:
            return [[timestamp, fake_data()]]
        except:
            return []


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
        return dict((i, TransientStreamModel(self, i)) for i in metrics)


class MetricsContainerExtension(Subscription):
    implements(IContainerExtender)
    baseclass()

    def extend(self):
        return {'metrics': Metrics(self.context)}


class ModelStream(TransientStream):
    context(Model)


@subscribe(IModel, IModelModifiedEvent)
def model_modified(model, event):
    if IStream.providedBy(model) or queryAdapter(model, IStream):
        timestamp = int(time.time() * 1000)
        for k in event.modified:
            IStream(model).add((timestamp, dict(event='change', name=k, value=event.modified[k],
                                                old_value=event.original[k])))


@subscribe(IModel, IModelCreatedEvent)
def model_created(model, event):
    from opennode.oms.model.traversal import canonical_path
    timestamp = int(time.time() * 1000)

    parent = event.container
    if IStream.providedBy(parent) or queryAdapter(parent, IStream):
        IStream(parent).add((timestamp, dict(event='add', name=model.__name__,
                                             url=canonical_path(model))))


@subscribe(IModel, IModelDeletedEvent)
def model_deleted(model, event):
    from opennode.oms.model.traversal import canonical_path
    timestamp = int(time.time() * 1000)

    parent = event.container
    if IStream.providedBy(parent) or queryAdapter(parent, IStream):
        IStream(parent).add((timestamp, dict(event='remove', name=model.__name__,
                                             url=canonical_path(parent))))

    if IStream.providedBy(model) or queryAdapter(model, IStream):
        IStream(model).add((timestamp, dict(event='delete', name=model.__name__,
                                            url=canonical_path(model))))
