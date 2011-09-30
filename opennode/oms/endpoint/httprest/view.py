from grokcore.component import context

from opennode.oms.endpoint.httprest.base import HttpRestView, IHttpRestView
from opennode.oms.model.location import ILocation
from opennode.oms.model.model import Computes, Compute, OmsRoot, Templates


class RootView(HttpRestView):
    context(OmsRoot)

    def render(self, request):
        return dict((name, ILocation(self.context[name]).get_url()) for name in self.context.listnames())



class ComputesView(HttpRestView):
    context(Computes)

    def render(self, request):
        all_computes = self.context.listcontent()
        q = request.args.get('q', [''])[0]
        q = q.decode('utf-8')

        if q:
            computes = []
            keywords = [i.lower() for i in q.split(' ') if i]
            for compute in all_computes:
                for keyword in keywords:
                    if (keyword in compute.type.lower()
                        or keyword in compute.hostname.lower()
                        or compute.ip_address.startswith(keyword)
                        or keyword in compute.architecture.lower()
                        or keyword == compute.state.lower()):
                        computes.append(compute)
        else:
            computes = all_computes

        return [IHttpRestView(compute).render(request) for compute in computes]


class ComputeView(HttpRestView):
    context(Compute)

    def render(self, request):
        return {'id': self.context.__name__,
                'hostname': self.context.hostname,
                'ip_address': self.context.ip_address,
                'url': ILocation(self.context).get_url(),
                'type': self.context.type,
                'state': self.context.state,

                'cpu': self.context.cpu,
                'memory': self.context.memory,
                'os_release': self.context.os_release,
                'kernel': self.context.kernel,
                'network': self.context.network,
                'diskspace': self.context.diskspace,
                'swap_size': self.context.swap_size,
                'diskspace_rootpartition': self.context.diskspace_rootpartition,
                'diskspace_storagepartition': self.context.diskspace_storagepartition,
                'diskspace_vzpartition': self.context.diskspace_vzpartition,
                'diskspace_backuppartition': self.context.diskspace_backuppartition,
                'startup_timestamp': self.context.startup_timestamp,
                }


class TemplatesView(HttpRestView):
    context(Templates)

    def render(self, request):
        return [{'name': name} for name in self.context.listnames()]



#~ # TODO: Move to a future config file/module.
#~ DEBUG = True


#~ class ComputeListResource(resource.Resource):

#~     def __init__(self, avatar=None):
#~         ## Twisted Resource is a not a new style class, so emulating a super-call
#~         resource.Resource.__init__(self)

#~         # TODO: This should be handled generically.
#~         self.avatar = avatar

#~     def getChild(self, path, request):
#~         # TODO: This should be handled generically.
#~         if not path: return self  # For trailing slahses.

#~         # TODO: This should be handled generically.
#~         return ComputeItemResource(path, avatar=self.avatar)

#~     def render_POST(self, request):
#~         # TODO: This should be handled generically.
#~         data = dict((k, request.args.get(k, [None])[0])
#~                     for k in ['name', 'hostname', 'ip', 'category'])
#~         deferred = ComputeBO().create_compute(data)

#~         @deferred
#~         def on_success((success, ret)):
#~             if success:
#~                 request.setResponseCode(201, 'Created')
#~                 request.setHeader('Location', ret)
#~             else:
#~                 request.setResponseCode(400, 'Bad Request')
#~             request.finish()

#~         @deferred
#~         def on_error(failure):
#~             failure = str(failure)
#~             log.err("Failed to create Compute", failure)
#~             request.setResponseCode(500, 'Server Error')
#~             if DEBUG: request.write(failure)
#~             request.finish()

#~         return NOT_DONE_YET


#~     def render_GET(self, request):
#~         deferred = ComputeBO().get_compute_all_basic()

#~         @deferred
#~         def on_success(info):
#~             request.write(json.dumps(info, indent=2) + '\n')
#~             request.finish()

#~         @deferred
#~         def on_error(failure):
#~             failure = str(failure)
#~             log.err("Failed to retrieve Compute list", failure)
#~             request.setResponseCode(500, 'Server Error')
#~             if DEBUG: request.write(failure)
#~             request.finish()

#~         return NOT_DONE_YET


#~ class ComputeItemResource(resource.Resource):

#~     def __init__(self, compute_id, avatar):
#~         resource.Resource.__init__(self)
#~         # TODO: This should be handled generically.
#~         self.avatar = avatar
#~         try:
#~             self.compute_id = int(compute_id)
#~         except ValueError:
#~             self.compute_id = None

#~     def getChild(self, path, request):
#~         # TODO: This should be handled generically.
#~         if not path: return self  # For trailing slahses.

#~         # TODO: This should be handled generically.
#~         self.compute_id = None
#~         return self

#~     def render_GET(self, request):
#~         # TODO: This should be handled generically.
#~         if self.compute_id is None:
#~             request.setResponseCode(404, 'Not Found')
#~             return ''

#~         deferred = ComputeBO().get_compute_one_basic(self.compute_id)

#~         @deferred
#~         def on_success(info):
#~             if not info:
#~                 request.setResponseCode(404, 'Not Found')
#~                 request.finish()
#~             else:
#~                 #~ request.setHeader('Content-Type', 'application/json')
#~                 #~ request.setHeader('Content-length', len(json.dumps(info) + '\n'))
#~                 request.write(json.dumps(info, indent=2) + '\n')
#~                 request.finish()

#~         @deferred
#~         def on_error(failure):
#~             failure = str(failure)
#~             log.err("Failed to retrieve Compute with ID %s" % self.compute_id, failure)
#~             request.setResponseCode(500, 'Server Error')
#~             if DEBUG: request.write(failure)
#~             request.finish()

#~         return NOT_DONE_YET
