from __future__ import absolute_import

from func import jobthing
from func.overlord.client import Overlord
from grokcore.component import Adapter, context, baseclass
from twisted.internet import defer, reactor
from zope.interface import classImplements

from opennode.oms.backend.operation import IFuncInstalled, IGetComputeInfo, IStartVM, IShutdownVM, IDestroyVM, ISuspendVM, IResumeVM, IRebootVM, IListVMS, IHostInterfaces, IDeployVM,  IUndeployVM, IGetGuestMetrics, IGetLocalTemplates
from opennode.oms.model.model.proc import Proc
from opennode.oms.zodb import db


class FuncBase(Adapter):
    """Base class for all Func method calls."""
    context(IFuncInstalled)
    baseclass()

    func_action = None
    interval = 0.1

    def run(self, *args, **kwargs):
        self.deferred = defer.Deferred()

        @db.ro_transact
        def spawn_func():
            client = self._get_client()
            # we assume that all of the func actions are in the form of 'module.action'
            module_action, action_name = self.func_action.rsplit('.', 1)
            module = getattr(client, module_action)
            action = getattr(module, action_name)

            self.job_id = action(*args, **kwargs)

            Proc.register(self.deferred, "/bin/func '%s' call %s %s" % (self.context.hostname.encode('utf-8'), self.func_action, ' '.join(map(str, args))))

            self.start_polling()

        spawn_func()
        return self.deferred

    @db.ro_transact
    def start_polling(self):
        return_code, results = self._get_client().job_status(self.job_id)

        if return_code in (jobthing.JOB_ID_FINISHED, jobthing.JOB_ID_REMOTE_ERROR):
            self._fire_events(results)
            return
        if return_code == jobthing.JOB_ID_LOST_IN_SPACE:
            self.deferred.errback(Exception('Command lost in space'))
            return
        reactor.callLater(self.interval, self.start_polling)

    def _fire_events(self, data):
        # noglobs=True and async=True cannot live together
        # see http://goo.gl/UgrZu
        # thus we need a robust way to get the result for this host,
        # even when the host names don't match (e.g. localhost vs real host name).
        hostkey = self.context.hostname
        if len(data.keys()) == 1:
            hostkey = data.keys()[0]
        res = data[hostkey]

        if res and isinstance(res, list) and res[0] == 'REMOTE_ERROR':
            self.deferred.errback(Exception(*res[1:]))
        else:
            self.deferred.callback(res)

    overlords = {}

    @db.assert_transact
    def _get_client(self):
        """Returns an instance of the Overlord."""
        if self.context.hostname not in self.overlords:
            self.overlords[self.context.hostname] = Overlord(self.context.hostname, async=True)
        return self.overlords[self.context.hostname]


FUNC_ACTIONS = {IGetComputeInfo: 'hardware.info', IStartVM: 'onode.vm.start_vm',
                IShutdownVM: 'onode.vm.shutdown_vm', IDestroyVM: 'onode.vm.destroy_vm',
                ISuspendVM: 'onode.vm.suspend_vm', IResumeVM: 'onode.vm.resume_vm',
                IRebootVM: 'onode.vm.reboot_vm', IListVMS: 'onode.vm.list_vms',
                IDeployVM: 'onode.vm.deploy_vm', IUndeployVM: 'onode.vm.undeploy_vm',
                IGetGuestMetrics: 'onode.vm.metrics',
                IGetLocalTemplates: 'onode.vm.get_local_templates',
                IHostInterfaces: 'onode.host.interfaces'}


# Avoid polluting the global namespace with temporary variables:
def _generate_classes():
    # Dynamically generate an adapter class for each supported Func function:
    for interface, action in FUNC_ACTIONS.items():
        cls_name = 'Func%s' % interface.__name__[1:]
        cls = type(cls_name, (FuncBase, ), dict(func_action=action))
        classImplements(cls, interface)
        globals()[cls_name] = cls
_generate_classes()
