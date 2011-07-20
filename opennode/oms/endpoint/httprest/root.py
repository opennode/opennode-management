import json

from twisted.web import resource
from twisted.web.server import NOT_DONE_YET
from twisted.internet import defer

from opennode.oms import db
from opennode.oms.endpoint.httprest.base import IHttpRestView
from opennode.oms.model.root import Root
from opennode.oms.model.traversal import ITraverser


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
        try:
            ret = yield self.handle_request(request)
            if ret is not None:
                response_text = json.dumps(ret, indent=2)
                response_text += '\n'
                request.write(response_text)
            else:
                request.setResponseCode(404, 'Not Found')
                request.write('404 Not Found\n')
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

        store = db.get_store()

        obj, unresolved_path = self.traverse(store, request.path)

        if not obj or unresolved_path:
            return None
        else:
            view = IHttpRestView(obj)
            return view.render(request, store)

    def traverse(self, store, path):
        """Using the given store, traverses the objects in the
        database to find an object that matches the given path.

        Returns the object up to which the traversal was successful,
        and the part of the path that could not be resolved.

        """

        path = path.split('/')[1:]

        # Allow one extra slash at the end:
        if path[-1] == '': path.pop()

        obj = Root()
        while path:
            name = path[0]
            traverser = ITraverser(obj)

            next_obj = traverser.traverse(name, store=store)

            if not next_obj: break

            obj = next_obj
            path = path[1:]

        return obj, path
