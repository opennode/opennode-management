import json

from grokcore.component import context
from zope.component import queryAdapter

from opennode.oms.endpoint.httprest.base import HttpRestView, IHttpRestView
from opennode.oms.model.form import ApplyRawData
from opennode.oms.model.location import ILocation
from opennode.oms.model.model import Machines, Compute
from opennode.oms.model.model.actions import ActionsContainer
from opennode.oms.model.model.base import IContainer
from opennode.oms.model.model.byname import ByNameContainer
from opennode.oms.model.model.filtrable import IFiltrable
from opennode.oms.model.model.hangar import Hangar
from opennode.oms.model.model.symlink import follow_symlinks
from opennode.oms.model.model.virtualizationcontainer import VirtualizationContainer
from opennode.oms.model.schema import model_to_dict


class DefaultView(HttpRestView):
    context(object)

    def render_GET(self, request):
        data = model_to_dict(self.context)

        data['id'] = self.context.__name__
        data['__type__'] = type(self.context).__name__
        data['url'] = ILocation(self.context).get_url()
        # XXX: Temporary hack--simplejson can't serialize sets
        if 'tags' in data:
            data['tags'] = list(data['tags'])

        return data

    def render_PUT(self, request):
        data = json.load(request.content)

        form = ApplyRawData(data, obj=self.context)
        if not form.errors:
            form.apply()
        else:
            return form.error_dict()

        return json.dumps('ok')


class ContainerView(DefaultView):
    context(IContainer)

    def render_GET(self, request):
        depth = request.args.get('depth', ['0'])[0]
        try:
            depth = int(depth)
        except ValueError:
            depth = 0
        return self.render_recursive(request, depth, top_level=True)

    def render_recursive(self, request, depth, top_level=False):
        container_properties = super(ContainerView, self).render_GET(request)

        if depth < 1:
            return container_properties

        items = map(follow_symlinks, self.context.listcontent())

        q = request.args.get('q', [''])[0]
        q = q.decode('utf-8')

        if q:
            items = [item for item in items if IFiltrable(item).match(q)]

        children = [IHttpRestView(item).render_recursive(request, depth - 1)
                    for item in items
                    if queryAdapter(item, IHttpRestView) and not self.blacklisted(item)]

        # backward compatibility:
        # top level results for pure containers are plain lists
        if top_level and (not container_properties or len(container_properties.keys()) == 1):
            return children

        #if not top_level or depth > 1:
        #if depth > 1:
        if not top_level or depth > 0:
            container_properties['children'] = children
        return  container_properties

    def blacklisted(self, item):
        return isinstance(item, ByNameContainer)


class MachinesView(ContainerView):
    context(Machines)

    def blacklisted(self, item):
        return super(MachinesView, self).blacklisted(item) or isinstance(item, Hangar)


class VirtualizationContainerView(ContainerView):
    context(VirtualizationContainer)

    def blacklisted(self, item):
        return (super(VirtualizationContainerView, self).blacklisted(item)
                or isinstance(item, ActionsContainer))


class ComputeView(ContainerView):
    context(Compute)

    def render_recursive(self, request, *args, **kwargs):
        ret = super(ComputeView, self).render_recursive(request, *args, **kwargs)

        ret.update({
            'features': [i.__name__ for i in self.context.implemented_interfaces()],
            'startup_timestamp': self.context.startup_timestamp,
        })
        return ret
