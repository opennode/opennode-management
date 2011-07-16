from twisted.python import log
from twisted.web import resource
from twisted.web.server import NOT_DONE_YET
from opennode.oms.bo.compute import ComputeBO

try:
    import json
except ImportError:
    import simplejson as json


class ComputeListResource(resource.Resource):

    def __init__(self, avatar = None):
        ## Twisted Resource is a not a new style class, so emulating a super-call
        resource.Resource.__init__(self)

        # TODO: This should be handled generically.
        self.avatar = avatar

    def getChild(self, path, request):
        # TODO: This should be handled generically.
        if not path: return self  # For trailing slahses.

        # TODO: This should be handled generically.
        return ComputeItemResource(path, avatar=self.avatar)

    def render_POST(self, request):
        """ Create a new compute instance """

        print "Creating a new instance."

    def render_GET(self, request):
        deferred = ComputeBO().get_compute_all_basic()

        @deferred
        def on_success(info):
            request.write(json.dumps(info, indent=2) + '\n')
            request.finish()

        @deferred
        def on_error(failure):
            log.err("Rendering failed", failure)
            request.write(str(failure))
            request.finish()

        return NOT_DONE_YET


class ComputeItemResource(resource.Resource):

    def __init__(self, compute_id, avatar):
        resource.Resource.__init__(self)
        # TODO: This should be handled generically.
        self.avatar = avatar
        try:
            self.compute_id = int(compute_id)
        except ValueError:
            self.compute_id = None

    def getChild(self, path, request):
        # TODO: This should be handled generically.
        if not path: return self  # For trailing slahses.

        # TODO: This should be handled generically.
        self.compute_id = None
        return self

    def render_GET(self, request):
        # TODO: This should be handled generically.
        if self.compute_id is None:
            request.setResponseCode(404, 'Not Found')
            return ''

        deferred = ComputeBO().get_compute_one_basic(self.compute_id)

        @deferred
        def on_success(info):
            if not info:
                request.setResponseCode(404, 'Not Found')
                request.finish()
            else:
                #~ request.setHeader('Content-Type', 'application/x-json')
                #~ request.setHeader('Content-length', len(json.dumps(info) + '\n'))
                request.write(json.dumps(info, indent=2) + '\n')
                request.finish()

        @deferred
        def on_error(failure):
            log.err("Rendering failed", failure)
            request.write(str(failure))
            request.finish()

        return NOT_DONE_YET
