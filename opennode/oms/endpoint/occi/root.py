from twisted.python import log
from twisted.web import resource
from twisted.web.server import NOT_DONE_YET

class OCCIServer(resource.Resource):
    '''
    Root resource for OMS.
    '''
    
    def __init__(self, dbpool):
        ## Twisted Resource is a not a new style class, so emulating a super-call
        resource.Resource.__init__(self)
        self.dbpool = dbpool
    
    def getChild(self, path, request):
        log.msg('Request received: %s, parameters: %s' %(request.path, request.args))
        return self
    
    def render(self, request):
        d = self.dbpool.runQuery('SELECT name FROM compute WHERE category=?', ["VM"])
        
        def _success(names):
            for vm in names:
                request.write(str(vm[0]))
            request.finish()        

        d.addCallback(_success)
        
        def _error(failure):
            log.err("Rendering failed", failure)
            request.write(str(failure))
            request.finish()
            
        d.addErrback(_error)
        
        return NOT_DONE_YET
        