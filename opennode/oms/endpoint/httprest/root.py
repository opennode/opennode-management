import json

from twisted.internet import defer, reactor
from twisted.web import resource
from twisted.web.server import NOT_DONE_YET
from twisted.python.failure import Failure
from zope.component import queryAdapter

from opennode.oms.endpoint.httprest.base import IHttpRestView
from opennode.oms.model.location import ILocation
from opennode.oms.model.traversal import traverse_path

from opennode.oms.zodb import db


class EmptyResponse(Exception):
    pass


class NotFound(Exception):
    pass


class NotImplemented(Exception):
    pass


class SeeCanonical(Exception):
    def __init__(self, url, *args, **kwargs):
        super(SeeCanonical, self).__init__(*args, **kwargs)
        self.url = url


class HttpRestServer(resource.Resource):
    """Restful HTTP API interface for OMS.

    Exposes a JSON web service to communicate with OMS.

    """

    def getChild(self, name, request):
        """We are the handler for anything below this base url, except what explicitly added in oms.tac."""
        return self

    def __init__(self, avatar=None):
        ## Twisted Resource is a not a new style class, so emulating a super-call
        resource.Resource.__init__(self)
        self.avatar = avatar

    def render(self, request):
        if request.method == 'OPTIONS':
            return self.render_OPTIONS(request)

        self._render(request)
        return NOT_DONE_YET

    def render_OPTIONS(self, request):
        """Return headers which allow cross domain xhr for this."""
        headers = request.responseHeaders
        headers.addRawHeader('Access-Control-Allow-Origin', '*')
        headers.addRawHeader('Access-Control-Allow-Methods', 'POST, OPTIONS')
        # this is necessary for firefox
        headers.addRawHeader('Access-Control-Allow-Headers', 'Origin, Content-Type, Cache-Control')
        # this is to adhere to the OPTIONS method, not necessary for cross-domain
        headers.addRawHeader('Allow', 'GET, POST, OPTIONS')

        return ""

    @defer.inlineCallbacks
    def _render(self, request):
        request.setHeader('Content-type', 'application/json')
        request.setHeader('Access-Control-Allow-Origin', '*')
        request.setHeader('Access-Control-Allow-Headers', 'X-Requested-With')

        ret = None
        try:
            ret = yield self.handle_request(request)
            if ret is EmptyResponse:
                raise ret
        except EmptyResponse:
            pass
        except NotFound:
            request.setResponseCode(404, "Not Found")
            request.write("404 Not Found\n")
        except SeeCanonical as exc:
            request.setResponseCode(301, 'Moved Permanently')
            request.setHeader('Location', exc.url)
            request.setResponseCode(501, "Not implemented")
        except NotImplemented as exc:
            request.write("Not implemented: %s" % exc.message)
        except Exception:
            Failure().printTraceback(request)
        else:
            # allow views to take full control of output streaming
            if ret != NOT_DONE_YET:
                request.write(json.dumps(ret, indent=2) + '\n')
        finally:
            if ret != NOT_DONE_YET:
                request.finish()

    @db.transact
    def handle_request(self, request):
        """Takes a request, maps it to a domain object and a
        corresponding IHttpRestView, and returns the rendered output
        of that view.

        """
        oms_root = db.get_root()['oms_root']
        objs, unresolved_path = traverse_path(oms_root, request.path[1:])
        if not objs:
            raise NotFound
        else:
            obj = objs[-1]

            view = queryAdapter(obj, IHttpRestView, name=unresolved_path[0] if unresolved_path else '')
            if not view:
                raise NotFound

            for method in ('render_' + request.method, 'render'):
                if hasattr(view, method):
                    return getattr(view, method)(request)

            raise NotImplemented("method %s not implemented\n" % request.method)
