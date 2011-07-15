from twisted.python import log
from twisted.web import resource
from opennode.oms.endpoint.occi.compute import ComputeResource


class OCCIServer(resource.Resource):
    """
    Root resource for OMS.
    """

    def __init__(self, dbpool):
        ## Twisted Resource is a not a new style class, so emulating a super-call
        resource.Resource.__init__(self)
        self.dbpool = dbpool

    def getChild(self, path, request):
        log.msg('Request received: %s, parameters: %s' % (request.path, request.args))
        # decide on the processor
        if path == 'compute':
            return ComputeResource(self.dbpool)
        return self

    def render(self, request):
        msg = "Unsupported operation: %s" % request.path
        log.err(msg)
        return msg
