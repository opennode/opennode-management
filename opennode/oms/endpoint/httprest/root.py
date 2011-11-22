import json

from twisted.internet import defer
from twisted.python.failure import Failure
from twisted.web import resource
from twisted.web.server import NOT_DONE_YET
from zope.component import queryAdapter

from opennode.oms.endpoint.httprest.base import IHttpRestView
from opennode.oms.model.traversal import traverse_path
from opennode.oms.zodb import db


class EmptyResponse(Exception):
    pass


class HttpStatus(Exception):
    @property
    def status_code(self):
        raise NotImplementedError

    @property
    def status_description(self):
        raise NotImplementedError


class NotFound(HttpStatus):
    status_code = 404
    status_description = "Not Found"


class NotImplemented(HttpStatus):
    status_code = 501
    status_description = "Not Implemented"


class SeeCanonical(HttpStatus):
    status_code = 301
    status_description = "Moved Permanently"

    def __init__(self, url, *args, **kwargs):
        super(SeeCanonical, self).__init__(*args, **kwargs)
        self.url = url


class BadRequest(HttpStatus):
    status_code = 400
    status_description = "Bad Request"


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
        self._render(request)
        return NOT_DONE_YET

    @defer.inlineCallbacks
    def _render(self, request):
        request.setHeader('Content-type', 'application/json')
        request.setHeader('Access-Control-Allow-Origin', '*')
        request.setHeader('Access-Control-Allow-Methods', 'GET, PUT, POST, DELETE, OPTIONS, HEAD')
        request.setHeader('Access-Control-Allow-Headers', 'Origin, Content-Type, Cache-Control, X-Requested-With')

        ret = None
        try:
            ret = yield self.handle_request(request)
            if ret is EmptyResponse:
                raise ret
        except EmptyResponse:
            pass
        except HttpStatus as exc:
            request.setResponseCode(exc.status_code, exc.status_description)
            request.write("%s %s\n" % (exc.status_code, exc.status_description))
            if exc.message:
                request.write("%s\n" % exc.message)
        except Exception:
            request.setResponseCode(500, "Server Error")
            request.write("%s %s\n\n" % (500, "Server Error"))
            # TODO: if DEBUG:
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
