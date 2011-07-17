from zope.interface import Interface, implements


class IView(Interface):
    def render(request, store):
        pass


class View(object):
    implements(IView)

    def __init__(self, context):
        self.context = context
