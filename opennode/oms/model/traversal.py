from zope.interface import Interface, implements


class ITraverser(Interface):
    def traverse(name, store):
        pass


class Traverser(object):
    implements(ITraverser)

    def __init__(self, context):
        self.context = context
