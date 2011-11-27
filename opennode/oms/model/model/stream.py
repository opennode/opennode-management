from __future__ import absolute_import

from grokcore.component import Subscription, baseclass
from zope.component import queryAdapter
from zope.interface import implements

from .base import ReadonlyContainer, IModel, IContainerExtender


class IStream(IModel):
    def events(after):
        pass


class IMetrics(IModel):
    pass


class TransientStream(object):
    implements(IStream)

    def __init__(self, parent, name):
        self.__parent__ = parent
        self.__name__ = name

        self.data = []

    def events(self, after):
        print "GETTING EVENTS AFTER", after
        import random

        r = self.__name__
        if r.endswith('cpu_usage'):
            return random.random()
        if r.endswith('memory_usage'):
            return random.randint(0, 100)
        if r.endswith('network_usage'):
            return random.randint(0, 100)
        if r.endswith('diskspace_usage'):
            return random.random() * 0.5 + 600  # useful


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
