from grokcore.component import Adapter, implements, context
from twisted.internet import defer

from .virtualizationcontainer import IVirtualizationContainerSubmitter
from opennode.oms.backend.metrics import IMetricsGatherer
from opennode.oms.backend.operation import IFuncInstalled, IGetGuestMetrics
from opennode.oms.zodb import db
import time


class VirtualComputeMetricGatherer(Adapter):
    """Gathers VM metrics through functionality exposed by the host compute via func."""

    implements(IMetricsGatherer)
    context(IFuncInstalled)

    @defer.inlineCallbacks
    def gather(self):

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
                                streams.append((vm_metrics[k], (timestamp, data[k])))
            return streams

        # streams could defer the data appending but we don't care
        for stream, data_point in (yield get_streams()):
            stream.add(data_point)
