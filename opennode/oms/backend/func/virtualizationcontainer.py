import transaction

from grokcore.component import Adapter, context, implements
from twisted.internet import defer
from zope.interface import Interface

from opennode.oms.backend.operation import IListVMS, IHostInterfaces
from opennode.oms.model.model.actions import Action, action
from opennode.oms.model.model.virtualizationcontainer import IVirtualizationContainer
from opennode.oms.model.model.network import NetworkInterfaces, NetworkInterface, BridgeInterface
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
            cmd.write("%s\n" % (": ".join(msg for msg in e.args if (not msg.startswith('  File "/') if isinstance(msg, str)  else True))))
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

class SyncAction(Action):
    """Force vms sync + sync host info"""
    context(IVirtualizationContainer)

    action('sync')

    @defer.inlineCallbacks
    def execute(self, cmd, args):
        # sync host interfaces (this is not the right place, but ...)
        host_compute = self.context.__parent__
        job = IHostInterfaces(host_compute)
        ifaces = yield job.run()

        self._sync_ifaces(ifaces)

    @db.transact
    def _sync_ifaces(self, ifaces):
        host_compute = self.context.__parent__

        host_compute.interfaces = NetworkInterfaces()
        for interface in ifaces:
            cls = NetworkInterface
            if interface['type'] == 'bridge':
                cls = BridgeInterface

            iface_node = cls(interface['name'], None, interface['mac'], 'active')

            if interface.has_key('ip'):
                print  "SETTING IP ADDR", interface['ip']
                iface_node.ipv4_address = interface['ip']
            if interface['type'] == 'bridge':
                iface_node.members = interface['members']

            host_compute.interfaces.add(iface_node)

        transaction.commit()
