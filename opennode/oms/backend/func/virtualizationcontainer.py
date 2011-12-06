from grokcore.component import Adapter, context, implements
from twisted.internet import defer
from zope.interface import Interface, alsoProvides, noLongerProvides

from opennode.oms.backend.operation import IListVMS, IHostInterfaces
from opennode.oms.model.model.actions import Action, action
from opennode.oms.model.model.compute import IVirtualCompute, Compute, IDeployed, IUndeployed
from opennode.oms.model.model.network import NetworkInterfaces, NetworkInterface, BridgeInterface
from opennode.oms.model.model.symlink import Symlink, follow_symlinks
from opennode.oms.model.model.virtualizationcontainer import IVirtualizationContainer
from opennode.oms.util import blocking_yield
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

        max_key_len = max([0] + [len(vm['name']) for vm in vms])

        for vm in vms:
            vm['name'] = vm['name'].ljust(max_key_len)
            cmd.write("%(name)s:  state=%(state)s, run_state=%(run_state)s, uuid=%(uuid)s\n" % vm)

            if vm['consoles']:
                cmd.write(" %s    consoles:\n" % (' ' * max_key_len))
            for console in vm['consoles']:
                attrs = " ".join(["%s=%s" % pair for pair in console.items()])
                cmd.write(" %s      %s\n" % (' ' * max_key_len, attrs))


class SyncVmsAction(Action):
    """Force vms sync + sync host info"""
    context(IVirtualizationContainer)

    action('sync')

    @db.transact
    def execute(self, cmd, args):
        blocking_yield(self._execute(cmd, args))

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
        self._sync_vms_2(remote_vms)

    @db.transact
    def _sync_vms_2(self, remote_vms):
        local_vms = [i for i in self.context.listcontent() if IVirtualCompute.providedBy(i)]

        remote_uuids = set(i['uuid'] for i in remote_vms)
        local_uuids = set(i.__name__ for i in local_vms)

        machines = db.get_root()['oms_root'].machines

        for vm_uuid in remote_uuids.difference(local_uuids):
            remote_vm = [i for i in remote_vms if i['uuid'] == vm_uuid][0]

            existing_machine = follow_symlinks(machines['by-name'][remote_vm['name']])
            if existing_machine:
                # XXX: this VM is a nested VM, for now let's hack it this way
                new_compute = Symlink(existing_machine.__name__, existing_machine)
                self.context._add(new_compute)
            else:
                new_compute = Compute(remote_vm['name'], remote_vm['state'], 'linux')
                new_compute.__name__ = vm_uuid
                alsoProvides(new_compute, IVirtualCompute)
                alsoProvides(new_compute, IDeployed)
                self.context.add(new_compute)

        for vm_uuid in remote_uuids.intersection(local_uuids):
            noLongerProvides(self.context[vm_uuid], IUndeployed)
            alsoProvides(self.context[vm_uuid], IDeployed)

        for vm_uuid in local_uuids.difference(remote_uuids):
            noLongerProvides(self.context[vm_uuid], IDeployed)
            alsoProvides(self.context[vm_uuid], IUndeployed)
            self.context[vm_uuid].state = u'inactive'

        # sync each vm
        from opennode.oms.backend.func.compute import SyncAction
        for action in [SyncAction(i) for i in self.context.listcontent() if IVirtualCompute.providedBy(i)]:
            matching = [i for i in remote_vms if i['uuid'] == action.context.__name__]
            if not matching:
                continue
            remote_vm = matching[0]

            # todo delegate all this into the action itself
            default_console = action.default_console()
            action.sync_consoles()
            action.sync_vm(remote_vm)
            action.create_default_console(default_console)

    @db.transact
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
