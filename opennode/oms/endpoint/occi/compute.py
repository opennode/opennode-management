from twisted.python import log
from twisted.web import resource
from twisted.web.server import NOT_DONE_YET

try:
    import json
except ImportError:
    import simplejson as json


class ComputeResource(resource.Resource):
    """
    Operations on compute.
    """

    def __init__(self, dbpool):
        ## Twisted Resource is a not a new style class, so emulating a super-call
        resource.Resource.__init__(self)
        self.dbpool = dbpool

    def getChild(self, path, request):
        return self

    def render_GET(self, request):
        d = self.dbpool.runQuery('SELECT name FROM compute WHERE category=?', ["VM"])

        def on_success(names):
            res = {}
            for n in names:
                res[str(n[0])] = 'operating'
            request.write(json.dumps([res, res]))
            request.finish()
        d.addCallback(on_success)

        def on_error(failure):
            log.err("Rendering failed", failure)
            request.write(str(failure))
            request.finish()
        d.addErrback(on_error)

        return NOT_DONE_YET
