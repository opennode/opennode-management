from zope.interface import Interface, implements


class IHttpRestView(Interface):
    def render(request, store):
        pass


class HttpRestView(object):
    implements(IHttpRestView)

    def __init__(self, context):
        self.context = context
