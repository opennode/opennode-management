from zope.component import adapts, provideAdapter

from opennode.oms.model.traversal import Traverser
from opennode.oms.model.model import Model


class ModelTraverser(Traverser):
    adapts(Model)

    def traverse(self, name, store):
        if name == '..':
            if hasattr(self.context, 'parent'):
                return self.context.parent
            else:
                raise Exception('Traversal error: %s has no parent defined' % str(self.context.name))
        elif name == '.':
            return self.context
        else:
            return self.context[name]


provideAdapter(ModelTraverser)
