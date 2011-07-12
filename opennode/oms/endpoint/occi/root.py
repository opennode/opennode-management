from twisted.web import resource
from twisted.python import log

OCCI_SERVER_VERSION = '0.1'

class OCCI_server(resource.Resource):
    '''
    Root resource for OMS.
    '''
    
    def __init__(self, avatarID = None):
        ## Twisted Resource is a not a new style class, so emulating a super-call
        resource.Resource.__init__(self)
        self.avatarID = avatarID
        log.msg("Authenticated user: %s" % avatarID)
    
    def getChild(self, path, request):
        log.msg("Request received: %s, parameters: %s" %(request.path, request.args))
        return self

    def render(self, request):
        return "OpenNode Management Server OCCI Interface/%s" % OCCI_SERVER_VERSION 