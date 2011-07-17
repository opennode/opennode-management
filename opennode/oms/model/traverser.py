from zope.component import adapts, provideAdapter

from opennode.oms.model.root import Root, Compute, ComputeList
from opennode.oms.model.traversal import Traverser


class ComputeTraverser(Traverser):
    adapts(Compute)

    def traverse(self, name, store):
        return None


class ComputeListTraverser(Traverser):
    adapts(ComputeList)

    def traverse(self, name, store):
        try:
            compute_id = int(name)
            if compute_id < 0:
                raise ValueError()
        except ValueError:
            return None
        else:
            return Compute(compute_id)


class RootTraverser(Traverser):
    adapts(Root)

    def traverse(self, name, store):
        if name == 'compute':
            return ComputeList()



provideAdapter(RootTraverser)
provideAdapter(ComputeListTraverser)
provideAdapter(ComputeTraverser)
