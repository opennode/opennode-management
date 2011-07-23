import json

from twisted.internet import defer
from twisted.web import resource
from twisted.web.server import NOT_DONE_YET

from opennode.oms.db import db
from opennode.oms.endpoint.httprest.base import IHttpRestView
from opennode.oms.model.model import Root
from opennode.oms.model.traversal import traverse_path


class HttpRestServer(resource.Resource):
    """Restful HTTP API interface for OMS.

    Exposes a JSON web service to communicate with OMS.

    """

    isLeaf = True

    def __init__(self, avatar=None):
        ## Twisted Resource is a not a new style class, so emulating a super-call
        resource.Resource.__init__(self)
        self.avatar = avatar

    def render(self, request):
        self._render(request)
        return NOT_DONE_YET

    @defer.inlineCallbacks
    def _render(self, request):
        request.setHeader('Content-type', 'application/x-json')
        try:
            ret = yield self.handle_request(request)
            if ret is False:
                request.setResponseCode(404, 'Not Found')
                request.write('404 Not Found\n')
            elif ret is not None:
                response_text = json.dumps(ret, indent=2)
                response_text += '\n'
                request.write(response_text)
        except Exception as e:
            request.write(str(e))
        finally:
            request.finish()

    @db.transact
    def handle_request(self, request):
        """Takes a request, maps it to a domain object and a
        corresponding IHttpRestView, and returns the rendered output
        of that view.

        """

        objs, unresolved_path = traverse_path(Root(), request.path[1:])

        if not objs or unresolved_path:
            return False
        else:
            obj = objs[-1]
            if obj.get_path() != request.path:
                request.setResponseCode(301, 'See canonical URL')
                request.setHeader('Location', obj.get_path())
                return None

            view = IHttpRestView(obj)
            return view.render(request, store=db.get_store())
