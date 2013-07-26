import json
import os
import time
import Queue

from grokcore.component import context
from hashlib import sha1
from twisted.web.server import NOT_DONE_YET
from twisted.python import log
from twisted.internet import reactor, threads, defer
from zope.component import queryAdapter, handle
from zope.security.interfaces import Unauthorized
from zope.security.proxy import removeSecurityProxy

from opennode.oms.endpoint.httprest.base import HttpRestView, IHttpRestView
from opennode.oms.endpoint.httprest.root import BadRequest, NotFound
from opennode.oms.endpoint.ssh.cmd.security import effective_perms
from opennode.oms.endpoint.ssh.detached import DetachedProtocol
from opennode.oms.endpoint.ssh.cmdline import ArgumentParsingError
from opennode.oms.model.form import RawDataApplier
from opennode.oms.model.location import ILocation
from opennode.oms.model.model.base import IContainer
from opennode.oms.model.model.bin import ICommand
from opennode.oms.model.model.byname import ByNameContainer
from opennode.oms.model.model.events import ModelDeletedEvent
from opennode.oms.model.model.filtrable import IFiltrable
from opennode.oms.model.model.search import SearchContainer, SearchResult
from opennode.oms.model.model.stream import IStream, StreamSubscriber
from opennode.oms.model.model.symlink import Symlink, follow_symlinks
from opennode.oms.model.schema import model_to_dict
from opennode.oms.model.traversal import traverse_path
from opennode.oms.security.checker import get_interaction
from opennode.oms.zodb import db


class DefaultView(HttpRestView):
    context(object)

    def render_GET(self, request):
        if not request.interaction.checkPermission('view', self.context):
            raise NotFound()

        data = model_to_dict(self.context)

        data['id'] = self.context.__name__
        data['__type__'] = type(removeSecurityProxy(self.context)).__name__
        try:
            data['url'] = ILocation(self.context).get_url()
        except Unauthorized:
            data['url'] = ''

        interaction = get_interaction(self.context)
        data['permissions'] = effective_perms(interaction, self.context) if interaction else []

        # XXX: simplejson can't serialize sets
        if 'tags' in data:
            data['tags'] = list(data['tags'])

        return data

    def render_PUT(self, request):
        data = json.load(request.content)
        if 'id' in data:
            del data['id']

        data = self.put_filter_attributes(request, data)

        form = RawDataApplier(data, self.context)
        if not form.errors:
            form.apply()
            return [IHttpRestView(self.context).render_recursive(request, depth=0)]
        else:
            request.setResponseCode(BadRequest.status_code)
            return form.error_dict()

    def put_filter_attributes(self, request, data):
        """Offer the possibility to subclasses to massage the received json before default behavior."""
        return data

    def render_DELETE(self, request):
        force = request.args.get('force', ['false'])[0] == 'true'

        parent = self.context.__parent__
        del parent[self.context.__name__]

        try:
            handle(self.context, ModelDeletedEvent(parent))
        except Exception as e:
            if not force:
                raise e
            return {'status': 'failure'}

        return {'status': 'success'}


class ContainerView(DefaultView):
    context(IContainer)

    def render_GET(self, request):
        depth = request.args.get('depth', ['0'])[0]
        try:
            depth = int(depth)
        except ValueError:
            depth = 0

        return self.render_recursive(request, depth, top_level=True)

    def render_recursive(self, request, depth, filter_=[], top_level=False):
        container_properties = super(ContainerView, self).render_GET(request)

        if depth < 1:
            return self.filter_attributes(request, container_properties)

        exclude = [excluded.strip() for excluded in request.args.get('exclude', [''])[0].split(',')]

        def preconditions(obj):
            yield request.interaction.checkPermission('view', obj)
            yield obj.__name__ not in exclude
            yield obj.target.__parent__ == obj.__parent__ if type(obj) is Symlink else True

        items = map(follow_symlinks, filter(lambda obj: all(preconditions(obj)), self.context.listcontent()))

        def secure_render_recursive(item):
            try:
                return IHttpRestView(item).render_recursive(request, depth - 1)
            except Unauthorized:
                permissions = effective_perms(get_interaction(item), item)
                if 'view' in permissions:
                    return dict(access='denied', permissions=permissions,
                                __type__=type(removeSecurityProxy(item)).__name__)

        qlist = []
        limit = None
        offset = 0

        if top_level:
            qlist = request.args.get('q', [])
            qlist = map(lambda q: q.decode('utf-8'), qlist)
            limit = int(request.args.get('limit', [0])[0])
            offset = int(request.args.get('offset', [1])[0]) - 1
            if offset <= 0:
                offset = 0

        def secure_filter_match(item, q):
            try:
                return IFiltrable(item).match(q)
            except Unauthorized:
                return

        for q in qlist:
            items = filter(lambda item: secure_filter_match(item, q), items)

        children = filter(None, [secure_render_recursive(item) for item in items
                                 if queryAdapter(item, IHttpRestView) and not self.blacklisted(item)])

        total_children = len(children)

        if (limit is not None and limit != 0) or offset:
            children = children[offset : offset + limit]

        # backward compatibility:
        # top level results for pure containers are plain lists
        if top_level and (not container_properties or len(container_properties.keys()) == 1):
            return children

        if not top_level or depth > 0:
            container_properties['children'] = children
            container_properties['totalChildren'] = total_children

        return self.filter_attributes(request, container_properties)

    def blacklisted(self, item):
        return isinstance(item, ByNameContainer)


class SearchView(ContainerView):
    context(SearchContainer)

    def render_GET(self, request):
        q = request.args.get('q', [''])[0]

        if not q:
            return super(SearchView, self).render_GET(request)

        search = db.get_root()['oms_root']['search']
        res = SearchResult(search, q.decode('utf-8'))

        return IHttpRestView(res).render_GET(request)


class StreamView(HttpRestView):
    context(StreamSubscriber)

    cached_subscriptions = dict()

    def rw_transaction(self, request):
        return False

    def render(self, request):
        timestamp = int(time.time() * 1000)
        oms_root = db.get_root()['oms_root']

        limit = int(request.args.get('limit', ['100'])[0])
        after = int(request.args.get('after', ['0'])[0])

        subscription_hash = request.args.get('subscription_hash', [''])[0]
        if subscription_hash:
            if subscription_hash in self.cached_subscriptions:
                data = self.cached_subscriptions[subscription_hash]
            else:
                raise BadRequest("Unknown subscription hash")
        elif not request.content.getvalue():
            return {}
        else:
            data = json.load(request.content)
            subscription_hash = sha1(request.content.getvalue()).hexdigest()
            self.cached_subscriptions[subscription_hash] = data
            request.responseHeaders.addRawHeader('X-OMS-Subscription-Hash', subscription_hash)

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


class CommandView(DefaultView):
    context(ICommand)

    def write_results(self, request, pid, cmd):
        log.msg('Called %s got result: pid(%s) term writes=%s' % (
                cmd, pid, len(cmd.write_buffer)), system='command-view')
        request.write(json.dumps({'status': 'ok', 'pid': pid,
                                  'stdout': cmd.write_buffer}))
        request.finish()

    def render_PUT(self, request):
        """ Converts arguments into command-line counterparts and executes the omsh command.

        Parameters passed as 'arg' are converted into positional arguments, others are converted into
        named parameters:

            PUT /bin/ls?arg=/some/path&arg=/another/path&-l&--recursive

        thus translates to:

            /bin/ls /some/path /another/path -l --recursive

        Allows blocking (synchronous) and non-blocking operation using the 'asynchronous' parameter (any
        value will trigger it). Synchronous operation requires two threads to function.
        """

        def named_args_filter_and_flatten(nargs):
            for name, vallist in nargs:
                if name not in ('arg', 'asynchronous'):
                    for val in vallist:
                        yield name
                        yield val

        def convert_args(args):
            tokenized_args = args.get('arg', [])
            return tokenized_args + list(named_args_filter_and_flatten(args.items()))

        protocol = DetachedProtocol()
        protocol.interaction = get_interaction(self.context) or request.interaction

        args = convert_args(request.args)
        args = filter(None, args)
        cmd = self.context.cmd(protocol)
        # Setting write_buffer to a list makes command save the output to the buffer too
        cmd.write_buffer = []
        d0 = defer.Deferred()

        try:
            pid = threads.blockingCallFromThread(reactor, cmd.register, d0, args,
                                                 '%s %s' % (request.path, args))
        except ArgumentParsingError, e:
            raise BadRequest(str(e))

        q = Queue.Queue()

        def execute(cmd, args):
            d = defer.maybeDeferred(cmd, *args)
            d.addBoth(q.put)
            d.chainDeferred(d0)

        dt = threads.deferToThread(execute, cmd, args)

        if request.args.get('asynchronous', []):
            reactor.callFromThread(self.write_results, request, pid, cmd)
        else:
            dt.addBoth(lambda r: threads.deferToThread(q.get, True, 60))
            dt.addCallback(lambda r: reactor.callFromThread(self.write_results, request, pid, cmd))

            def errhandler(e, pid, cmd):
                e.trap(ArgumentParsingError)
                raise BadRequest(str(e))
            dt.addErrback(errhandler, pid, cmd)
        return NOT_DONE_YET
