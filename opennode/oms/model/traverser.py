from zope.component import adapts, provideAdapter

from opennode.oms.model.traversal import Traverser
from opennode.oms.model.model import Model


class ModelTraverser(Traverser):
    """Generic traverser for all Model instances."""

    adapts(Model)

    def traverse(self, name, store):
        """Traverses the wrapped Model object using the given store to
        find the child object with the given name.

        Uses the `parent` property and the `__getitem__` accessor for traversal.

        Returns the wrapped object if `name` is `.`.

        """
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
