from grokcore.component import Adapter, implements, baseclass
from grokcore.security import require
from zope.interface import Interface


class IHttpRestView(Interface):
    def render(request):
        pass

    def render_recursive(request, depth):
        pass


class HttpRestView(Adapter):
    implements(IHttpRestView)
    baseclass()
    require('rest')

    def render_recursive(self, request, depth):
        return self.render_GET(request)

    def render_OPTIONS(self, request):
        all_methods = ['GET', 'POST', 'PUT', 'DELETE', 'HEAD']
        has_methods = [m for m in all_methods if hasattr(self, 'render_%s' % m)] + ['OPTIONS']
        request.setHeader('Allow', ', '.join(has_methods))

        from opennode.oms.endpoint.httprest.root import EmptyResponse
        return EmptyResponse
