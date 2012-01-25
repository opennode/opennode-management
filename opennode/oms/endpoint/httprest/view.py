import json
import time
import os

from grokcore.component import context
from zope.component import queryAdapter
from zope.security.proxy import removeSecurityProxy

from opennode.oms.endpoint.httprest.base import HttpRestView, IHttpRestView
from opennode.oms.endpoint.httprest.root import BadRequest
from opennode.oms.model.form import ApplyRawData
from opennode.oms.model.location import ILocation
from opennode.oms.model.model.base import IContainer
from opennode.oms.model.model.byname import ByNameContainer
from opennode.oms.model.model.search import SearchContainer, SearchResult
from opennode.oms.model.model.stream import IStream, StreamSubscriber
from opennode.oms.model.model.symlink import follow_symlinks
from opennode.oms.model.schema import model_to_dict
from opennode.oms.model.traversal import traverse_path
from opennode.oms.zodb import db


class DefaultView(HttpRestView):
    context(object)

    def render_GET(self, request):
        data = model_to_dict(self.context)

        data['id'] = self.context.__name__
        data['__type__'] = type(removeSecurityProxy(self.context)).__name__
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
            return [IHttpRestView(self.context).render_recursive(request, depth=0)]
        else:
            request.setResponseCode(BadRequest.status_code)
            return form.error_dict()


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


class SearchView(ContainerView):
    context(SearchContainer)

    def render_GET(self, request):
        q = request.args.get('q', [''])[0]
        q = q.decode('utf-8')

        if not q:
            return super(SearchView, self).render_GET(request)

        search = db.get_root()['oms_root']['search']
        res = SearchResult(search, q)

        return IHttpRestView(res).render_GET(request)


class StreamView(HttpRestView):
    context(StreamSubscriber)

    def render(self, request):
        timestamp = int(time.time() * 1000)
        oms_root = db.get_root()['oms_root']

        limit = int(request.args.get('limit', ['100'])[0])
        after = int(request.args.get('after', ['0'])[0])

        if not request.content.getvalue():
            return {}

        data = json.load(request.content)

        def val(r):
            objs, unresolved_path = traverse_path(oms_root, r)
            if unresolved_path:
                return [(timestamp, dict(event='delete', name=os.path.basename(r), url=r))]
            return IStream(objs[-1]).events(after, limit=limit)

        # ONC wants it in ascending time order
        # while internally we prefer to keep it newest first to
        # speed up filtering.
        # Reversed is not json serializable so we have to reify to list.
        res = [list(reversed(val(resource))) for resource in data]
        res = [(i, v) for i, v in enumerate(res) if v]
        return [timestamp, dict(res)]
