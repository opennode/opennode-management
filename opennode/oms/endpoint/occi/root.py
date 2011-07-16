from twisted.python import log
from twisted.web import resource
from opennode.oms.endpoint.occi.compute import ComputeListResource


class OCCIServer(resource.Resource):
    """
    Root resource for OMS.
    """

    def __init__(self, avatar=None):
        ## Twisted Resource is a not a new style class, so emulating a super-call
        resource.Resource.__init__(self)
        self.avatar = avatar

    def getChild(self, path, request):
        log.msg('Request received: %s, parameters: %s' % (request.path, request.args))
        # decide on the processor
        if path == 'compute':
            return ComputeListResource()
        return self

    def render(self, request):
        request.setResponseCode(404, 'Not Found')
        return ''
