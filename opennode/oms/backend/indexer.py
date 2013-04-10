from collections import deque
from twisted.internet import defer
from twisted.python import log
from zope.component import provideSubscriptionAdapter
from zope.interface import implements
from zope.keyreference.interfaces import NotYet

from opennode.oms.endpoint.ssh.detached import DetachedProtocol
from opennode.oms.model.model.proc import IProcess, Proc, DaemonProcess
from opennode.oms.model.model.search import ReindexAction
from opennode.oms.util import subscription_factory, async_sleep
from opennode.oms.zodb import db
from opennode.oms.model.form import IModelDeletedEvent
from opennode.oms.model.traversal import canonical_path, traverse_path


class BlackHoleQueue(object):
    def append(self, val):
        pass


class IndexerDaemonProcess(DaemonProcess):
    implements(IProcess)

    __name__ = "indexer"

    queue = deque()

    black_hole = BlackHoleQueue()

    @defer.inlineCallbacks
    def run(self):
        while True:
            try:
                if not self.paused:
                    if IndexerDaemonProcess.queue == self.black_hole:
                        IndexerDaemonProcess.queue = deque()

                        self.reindex()
                        yield self.process()
                    else:
                        IndexerDaemonProcess.queue = self.black_hole

            except Exception:
                log.err(system='indexer')

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
        log.msg("indexing a batch of objects", system="indexer")

        searcher = db.get_root()['oms_root']['search']

        def currently_queued():
            while self.queue:
                yield self.queue.popleft()

        for model, event in currently_queued():
            self.index(searcher, model, event)

        log.msg("done", system="indexer")

    def index(self, searcher, model, event):
        if not self.try_index(searcher, model, event):
            log.msg("cannot (un)index %s %s" % (model, type(event).__name__), system="indexer")

    def try_index(self, searcher, model, event):
        path = canonical_path(model)
        op = 'un' if IModelDeletedEvent.providedBy(event) else ''

        log.msg("%sindexing %s %s" % (op, path, type(event).__name__), system="indexer")

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

        log.msg("%sindexed %s %s" % (op, path, type(event).__name__), system="indexer")
        return True

    def reindex(self):
        ReindexAction(None).execute(DetachedProtocol(), object())

provideSubscriptionAdapter(subscription_factory(IndexerDaemonProcess), adapts=(Proc,))
