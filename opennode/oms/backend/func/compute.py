from __future__ import absolute_import

from grokcore.component import subscribe

from opennode.oms.model.form import IModelModifiedEvent
from opennode.oms.model.model.compute import ICompute

from .virtualizationcontainer import IVirtualizationContainerSubmitter
from opennode.oms.backend.operation import IStartVM, IShutdownVM

from twisted.internet import defer


@subscribe(ICompute, IModelModifiedEvent)
@defer.inlineCallbacks
def handle_compute_state_change_request(compute, event):
    if not event.modified.get('state', None):
        return

    submitter = IVirtualizationContainerSubmitter(compute.__parent__)

    if event.original['state'] == 'inactive' and event.modified['state'] == 'active':
        action = IStartVM
    elif event.original['state'] == 'active' and event.modified['state'] == 'inactive':
        action = IShutdownVM
    else:
        return

    try:
        yield submitter.submit(action, compute.__name__)
    except Exception as e:
        compute.effective_state = event.original['state']
        raise e
    compute.effective_state = event.modified['state']

