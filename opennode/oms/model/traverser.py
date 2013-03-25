from grokcore.component import context

import opennode.oms.model.model.root
from opennode.oms.model.model.base import IContainer, IModel
from opennode.oms.model.traversal import Traverser


class ModelTraverser(Traverser):
    """Generic traverser for all IModel instances."""
    context(IModel)

    def traverse(self, name):
        """Traverses the object to find the next object in the path to
        traverse.

        Only traversing `.` and `..` is supported generically for all objects.

        """
        if name == '..':
            return self.context.__parent__
        elif name == '.':
            return self.context


class ContainerTraverser(ModelTraverser):
    """Generic traverser for all IContainer instances."""
    context(IContainer)

    def traverse(self, name):
        """Amends ModelTraverser.traverse to add the ability to
        traverse child objects in IContainer instances.

        Uses the `__parent__` property and the `__getitem__` accessor for traversal.

        """
        ret = super(ContainerTraverser, self).traverse(name)
        if ret is None:
            return self.context[name] if ret is None else ret
        else:
            return ret


class RootTraverser(ContainerTraverser):
    context(opennode.oms.model.model.root.OmsRoot)

    def traverse(self, name):
        if name == '..':
            return self.context
        else:
            return super(RootTraverser, self).traverse(name)
