from grokcore.component import Adapter, implements, context
from twisted.internet import defer

from .virtualizationcontainer import IVirtualizationContainerSubmitter
from opennode.oms.backend.metrics import IMetricsGatherer
from opennode.oms.backend.operation import IFuncInstalled, IGetGuestMetrics, IGetHostMetrics
from opennode.oms.model.model.stream import IStream
from opennode.oms.zodb import db
import time


class VirtualComputeMetricGatherer(Adapter):
    """Gathers VM metrics through functionality exposed by the host compute via func."""

    implements(IMetricsGatherer)
    context(IFuncInstalled)

    @defer.inlineCallbacks
    def gather(self):
        yield self.gather_vms()
        yield self.gather_phy()

    @defer.inlineCallbacks
    def gather_vms(self):

        @db.ro_transact
        def get_vms():
            return self.context['vms']
        vms = yield get_vms()

        # get the metrics for all running VMS
        if not vms or self.context.state != u'active':
            return
        metrics = yield IVirtualizationContainerSubmitter(vms).submit(IGetGuestMetrics)

        timestamp = int(time.time() * 1000)

        # db transact is needed only to traverse the zodb.
        @db.ro_transact
        def get_streams():
            streams = []
            for uuid, data in metrics.items():
                vm = vms[uuid]
                if vm:
                    vm_metrics = vm['metrics']
                    if vm_metrics:
                        for k in data:
                            if vm_metrics[k]:
                                streams.append((IStream(vm_metrics[k]), (timestamp, data[k])))
            return streams

        # streams could defer the data appending but we don't care
        for stream, data_point in (yield get_streams()):
            stream.add(data_point)

    @defer.inlineCallbacks
    def gather_phy(self):
        try:
            data = yield IGetHostMetrics(self.context).run()
            print "[metrics] got phy metrics:", data

            timestamp = int(time.time() * 1000)

            # db transact is needed only to traverse the zodb.
            @db.ro_transact
            def get_streams():
                streams = []
                host_metrics = self.context['metrics']
                if host_metrics:
                    for k in data:
                        if host_metrics[k]:
                            streams.append((IStream(host_metrics[k]), (timestamp, data[k])))

                return streams

            for stream, data_point in (yield get_streams()):
                stream.add(data_point)

        except Exception as e:
            if False:
                print "[metrics] cannot gather phy metrics", e
