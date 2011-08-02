import json

from twisted.internet import defer, reactor
from twisted.web import resource
from twisted.web.server import NOT_DONE_YET
from twisted.python.failure import Failure

from opennode.oms.endpoint.httprest.base import IHttpRestView
from opennode.oms.model.location import ILocation
from opennode.oms.model.traversal import traverse_path
from opennode.oms.zodb import db


class EmptyResponse(Exception):
    pass


class NotFound(Exception):
    pass


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
            if ret is EmptyResponse:
                raise ret
        except EmptyResponse:
            pass
        except NotFound:
            request.setResponseCode(404, "Not Found")
            request.write("404 Not Found\n")
        except Exception:
            Failure().printDetailedTraceback(request)
        else:
            request.write(json.dumps(ret, indent=2) + '\n')
        finally:
            request.finish()

    @db.transact
    def handle_request(self, request):
        """Takes a request, maps it to a domain object and a
        corresponding IHttpRestView, and returns the rendered output
        of that view.

        """
        oms_root = db.get_root()['oms_root']
        objs, unresolved_path = traverse_path(oms_root, request.path[1:])
        if not objs or unresolved_path:
            raise NotFound
        else:
            obj = objs[-1]
            loc = ILocation(obj)

            if loc.get_url() != request.path:
                reactor.callFromThread(request.setResponseCode, 301, 'See canonical URL')
                reactor.callFromThread(request.setHeader, 'Location', loc.get_url())
                return EmptyResponse

            view = IHttpRestView(obj)
            return view.render(request)
