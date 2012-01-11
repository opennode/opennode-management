from collections import deque
from twisted.internet import defer
from zope.component import provideSubscriptionAdapter
from zope.interface import implements
from zope.keyreference.interfaces import NotYet

from opennode.oms.model.model.proc import IProcess, Proc, DaemonProcess
from opennode.oms.util import subscription_factory, async_sleep
from opennode.oms.zodb import db
from opennode.oms.model.form import IModelDeletedEvent
from opennode.oms.model.traversal import canonical_path, traverse_path


class IndexerDaemonProcess(DaemonProcess):
    implements(IProcess)

    __name__ = "indexer"

    queue = deque()

    @defer.inlineCallbacks
    def run(self):
        while True:
            try:
                if not self.paused:
                    yield self.process()
            except Exception:
                import traceback
                traceback.print_exc()
                pass

            yield async_sleep(1)

    @classmethod
    def enqueue(cls, model, event):
        cls.queue.append((model, event))

    @defer.inlineCallbacks
    def process(self):
        if self.queue:
            yield self._process()

    @db.transact
    def _process(self):
        print "[indexer] indexing a batch of objects"

        searcher = db.get_root()['oms_root']['search']

        def currently_queued():
            while self.queue:
                yield self.queue.popleft()

        for model, event in currently_queued():
            self.index(searcher, model, event)

        print "[indexer] done"

    def index(self, searcher, model, event):
        if not self.try_index(searcher, model, event):
            print "[indexer] cannot (un)index", model, type(event).__name__

    def try_index(self, searcher, model, event):
        path = canonical_path(model)
        op = 'un' if IModelDeletedEvent.providedBy(event) else ''

        print "[indexer] %sindexing" % op, path, type(event).__name__

        objs, unresolved_path = traverse_path(db.get_root()['oms_root'], path)
        if unresolved_path and not IModelDeletedEvent.providedBy(event):
            return False

        obj = objs[-1]

        try:
            if IModelDeletedEvent.providedBy(event):
                searcher.unindex_object(obj)
            else:
                searcher._index_object(obj)
        except NotYet:
            return False

        print "[indexer] %sindexed" % op, path, type(event).__name__

        return True


provideSubscriptionAdapter(subscription_factory(IndexerDaemonProcess), adapts=(Proc,))
