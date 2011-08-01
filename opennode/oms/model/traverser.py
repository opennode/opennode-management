from zope.component import adapts, provideAdapter

from opennode.oms.model.traversal import Traverser
from opennode.oms.model.model import OmsRoot
from opennode.oms.model.model import IContainer


class ContainerTraverser(Traverser):
    """Generic traverser for all Model instances."""

    adapts(IContainer)

    def traverse(self, name):
        """Traverses the wrapped Model object using the given store to
        find the child object with the given name.

        Uses the `parent` property and the `__getitem__` accessor for traversal.

        Returns the wrapped object if `name` is `.`.

        """
        if name == '..':
            return self.context.__parent__
        elif name == '.':
            return self.context
        else:
            return self.context[name]


class RootTraverser(ContainerTraverser):
    adapts(OmsRoot)

    def traverse(self, name):
        if name == '..':
            return self.context
        else:
            return super(RootTraverser, self).traverse(name)


provideAdapter(ContainerTraverser)
provideAdapter(RootTraverser)
