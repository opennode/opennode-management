from twisted.python import log
from twisted.web import resource
from twisted.web.server import NOT_DONE_YET
from opennode.oms.bo import compute

try:
    import json
except ImportError:
    import simplejson as json


class ComputeResource(resource.Resource):
    """
    Operations on compute.
    """

    def __init__(self, avatar = None):
        ## Twisted Resource is a not a new style class, so emulating a super-call
        resource.Resource.__init__(self)
        self.avatar = avatar

    def getChild(self, path, request):
        return self

    def render_POST(self, request):
        """ Create a new compute instance """

        print "Creating a new instance."
    def render_GET(self, id, request):
        print "Getting compute id: ", id
        d = compute.get_compute_basic(id)

        @d.addCallback
        def on_success(info):
            request.write(json.dumps(info))
            request.finish()

        @d.addErrback
        def on_error(failure):
            log.err("Rendering failed", failure)
            request.write(str(failure))
            request.finish()

        return NOT_DONE_YET

