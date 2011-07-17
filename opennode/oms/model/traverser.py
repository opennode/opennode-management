from zope.component import adapts, provideAdapter

from opennode.oms.model.base import Model
from opennode.oms.model.traversal import Traverser


class ModelTraverser(Traverser):
    adapts(Model)

    def traverse(self, name, store):
        return self.context[name]


provideAdapter(ModelTraverser)
