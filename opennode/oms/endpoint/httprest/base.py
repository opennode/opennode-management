from zope.interface import Interface, implements


class IHttpRestView(Interface):
    def render(request):
        pass


class HttpRestView(object):
    implements(IHttpRestView)

    def __init__(self, context):
        self.context = context
