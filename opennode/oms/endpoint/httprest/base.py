from grokcore.component import Adapter, implements
from zope.interface import Interface


class IHttpRestView(Interface):
    def render(request):
        pass


class HttpRestView(Adapter):
    implements(IHttpRestView)
