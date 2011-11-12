from grokcore.component import Adapter, context, implements
from twisted.internet import defer
from zope.interface import Interface, alsoProvides

from opennode.oms.backend.operation import IListVMS, IHostInterfaces
from opennode.oms.model.model.actions import Action, action
from opennode.oms.model.model.compute import IVirtualCompute, Compute
from opennode.oms.model.model.network import NetworkInterfaces, NetworkInterface, BridgeInterface
from opennode.oms.model.model.virtualizationcontainer import IVirtualizationContainer
from opennode.oms.zodb import db


backends = {'test': 'test:///tmp/func_vm_test_state.xml',
            'openvz': 'openvz:///system',
            'kvm': 'qemu:///system',
            'xen': 'xen:///'}


class IVirtualizationContainerSubmitter(Interface):
    def submit(job_interface):
        """Submits a job to the virtualization container"""


class FuncVirtualizationContainerSubmitter(Adapter):
    implements(IVirtualizationContainerSubmitter)
    context(IVirtualizationContainer)

    def submit(self, job_interface, *args):
        job = job_interface(self.context.__parent__)
        backend_uri = backends.get(self.context.backend, self.context.backend)
        return job.run(backend_uri, *args)


class ListVirtualizationContainerAction(Action):
    """Lists the content of a virtualizationcontaineraction.
    Usually the zodb will be in sync, but it can be useful to see real time info (perhaps just for test)."""

    context(IVirtualizationContainer)
    action('list')

    @defer.inlineCallbacks
    def execute(self, cmd, args):
        cmd.write("listing virtual machines\n")
        submitter = IVirtualizationContainerSubmitter(self.context)

        try:
            vms = yield submitter.submit(IListVMS)
        except Exception as e:
            cmd.write("%s\n" % (": ".join(str(msg) for msg in e.args if (not msg.startswith('  File "/') if isinstance(msg, str)  else True))))
            return

        max_key_len = max(len(vm['name']) for vm in vms)

        for vm in vms:
            vm['name'] = vm['name'].ljust(max_key_len)
            cmd.write("%(name)s:  state=%(state)s, run_state=%(run_state)s, uuid=%(uuid)s\n" % vm)

            if vm['consoles']:
                cmd.write(" %s    consoles:\n" % (' '*max_key_len))
            for console in vm['consoles']:
                attrs = " ".join(["%s=%s" % pair for pair in console.items()])
                cmd.write(" %s      %s\n" % (' '*max_key_len, attrs))


class SyncVmsAction(Action):
    """Force vms sync + sync host info"""
    context(IVirtualizationContainer)

    action('sync')

    @db.transact
    def execute(self, cmd, args):
        deferred = self._execute(cmd, args)
        import time
        while not deferred.called:
            time.sleep(0.1)

    @defer.inlineCallbacks
    def _execute(self, cmd, args):
        # sync host interfaces (this is not the right place, but ...)
        host_compute = self.context.__parent__
        job = IHostInterfaces(host_compute)
        ifaces = yield job.run()

        yield self._sync_ifaces(ifaces)

        # sync virtual computes
        yield self._sync_vms(cmd)

    @defer.inlineCallbacks
    def _sync_vms(self, cmd):
        submitter = IVirtualizationContainerSubmitter(self.context)

        remote_vms = yield submitter.submit(IListVMS)
        local_vms = [i for i in self.context.listcontent() if IVirtualCompute.providedBy(i)]

        remote_uuids = set(i['uuid'] for i in remote_vms)
        local_uuids = set(i.__name__ for i in local_vms)

        for vm_uuid in remote_uuids.difference(local_uuids):
            remote_vm = [i for i in remote_vms if i['uuid'] == vm_uuid][0]
            new_compute = Compute('linux', remote_vm['name'], 2000, remote_vm['state'])
            new_compute.__name__ = vm_uuid
            alsoProvides(new_compute, IVirtualCompute)
            self.context.add(new_compute)

        # sync each vm
        from opennode.oms.backend.func.compute import SyncAction
        for action in [SyncAction(i) for i in self.context.listcontent() if IVirtualCompute.providedBy(i)]:
            remote_vm = [i for i in remote_vms if i['uuid'] == action.context.__name__][0]

            # todo delegate all this into the action itself
            default_console = action.default_console()
            action.sync_consoles(cmd)
            action.sync_vm(cmd, remote_vm)
            action.create_default_console(default_console)

    def _sync_ifaces(self, ifaces):
        host_compute = self.context.__parent__

        host_compute.interfaces = NetworkInterfaces()
        for interface in ifaces:
            cls = NetworkInterface
            if interface['type'] == 'bridge':
                cls = BridgeInterface

            iface_node = cls(interface['name'], None, interface.get('mac', None), 'active')

            if interface.has_key('ip'):
                iface_node.ipv4_address = interface['ip']
            if interface['type'] == 'bridge':
                iface_node.members = interface['members']

            host_compute.interfaces.add(iface_node)

