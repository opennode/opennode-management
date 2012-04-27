from grokcore.component import Adapter, implements, baseclass
from grokcore.security import require
from zope.interface import Interface


class IHttpRestView(Interface):
    def render(request):
        pass

    def render_recursive(request, depth):
        pass

    def rw_transaction(request):
        """Return true if we this request should be committed"""


class IHttpRestSubViewFactory(Interface):
    def resolve(path):
        """Resolve a view for a given sub path"""


class HttpRestView(Adapter):
    implements(IHttpRestView)
    baseclass()
    require('rest')

    __builtin_attributes__ = ['id', 'children']

    def filter_attributes(self, request, data):
        """Handle the filtering of attributes according to the 'attrs' parameter in the request"""
        attrs = request.args.get('attrs', [''])[0]
        if attrs:
            filtered_data = {}
            for a in attrs.decode('utf-8').split(',') + self.__builtin_attributes__:
                if a in data:
                    filtered_data[a] = data[a]
            return filtered_data
        return data

    def render_recursive(self, request, depth):
        for method in ('render_' + request.method, 'render'):
            if hasattr(self, method):
                return self.filter_attributes(request, getattr(self, method)(request))
        raise NotImplemented("method %s not implemented\n" % request.method)

    def render_OPTIONS(self, request):
        all_methods = ['GET', 'POST', 'PUT', 'DELETE', 'HEAD']
        has_methods = [m for m in all_methods if hasattr(self, 'render_%s' % m)] + ['OPTIONS']
        request.setHeader('Allow', ', '.join(has_methods))

        from opennode.oms.endpoint.httprest.root import EmptyResponse
        return EmptyResponse

    def rw_transaction(self, request):
        return request.method != 'GET'
