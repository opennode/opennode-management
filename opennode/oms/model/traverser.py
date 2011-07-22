from zope.component import adapts, provideAdapter

from opennode.oms.model.traversal import Traverser
from opennode.oms.model.model import Model


class ModelTraverser(Traverser):
    adapts(Model)

    def traverse(self, name, store):
        return self.context[name]

    def list(self, store):
        return list(self.context)


provideAdapter(ModelTraverser)
