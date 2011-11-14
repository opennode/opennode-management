from grokcore.component import Adapter, implements, baseclass
from zope.interface import Interface


class IHttpRestView(Interface):
    def render(request):
        pass

    def render_recursive(request, depth):
        pass


class HttpRestView(Adapter):
    implements(IHttpRestView)
    baseclass()

    def render_recursive(self, request, depth):
        return self.render_GET(request)
