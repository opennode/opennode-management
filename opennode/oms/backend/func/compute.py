from __future__ import absolute_import

from grokcore.component import context, subscribe, baseclass
from twisted.internet import defer

from .virtualizationcontainer import IVirtualizationContainerSubmitter
from opennode.oms.backend.operation import IStartVM, IShutdownVM, IDestroyVM, ISuspendVM, IResumeVM, IListVMS, IRebootVM, IGetComputeInfo, IFuncInstalled
from opennode.oms.model.form import IModelModifiedEvent
from opennode.oms.model.model.actions import Action, action
from opennode.oms.model.model.compute import ICompute, IVirtualCompute
from opennode.oms.model.model.console import Consoles, TtyConsole, SshConsole, OpenVzConsole, VncConsole
from opennode.oms.model.model.network import NetworkInterfaces, NetworkInterface
from opennode.oms.model.model.symlink import Symlink
from opennode.oms.zodb import db


class SyncAction(Action):
    """Force compute sync"""
    context(ICompute)

    action('sync')

    @db.transact
    def execute(self, cmd, args):
        deferred = self._execute(cmd, args)
        import time
        while not deferred.called:
            time.sleep(0.1)

    @defer.inlineCallbacks
    def _execute(self, cmd, args):
        default = self.default_console()

        try:
            self.sync_consoles()
            self.sync_hw()

            if IVirtualCompute.providedBy(self.context):
                yield self._sync_virtual()

            yield self._create_default_console(default)

        except Exception as e:
            cmd.write("%s\n" % (": ".join(msg for msg in e.args if isinstance(msg, str) and not msg.startswith('  File "/'))))

    @db.assert_transact
    def default_console(self):
        default = self.context.consoles['default']
        if default:
            return default.target.__name__

    @db.transact
    def _create_default_console(self, default):
        self.create_default_console(default)

    @db.assert_transact
    def create_default_console(self, default):
        if not default or not self.context.consoles[default]:
            default = 'ssh'
        self.context.consoles.add(Symlink('default', self.context.consoles[default]))

    @db.assert_transact
    def sync_consoles(self):
        self.context.consoles = Consoles()
        ssh_console = SshConsole('ssh', 'root', self.context.hostname, 22)
        self.context.consoles.add(ssh_console)

    @db.assert_transact
    @defer.inlineCallbacks
    def _sync_virtual(self):
        submitter = IVirtualizationContainerSubmitter(self.context.__parent__)
        # TODO: not efficient but for now it's not important to add an ad-hoc func method for this.
        for vm in (yield submitter.submit(IListVMS)):
            if vm['uuid'] == self.context.__name__:
                yield self._sync_vm(vm)

    @db.transact
    def _sync_vm(self, vm):
        return self.sync_vm(vm)

    @db.assert_transact
    def sync_vm(self, vm):
        self.context.state = unicode(vm['state'])
        self.context.effective_state = self.context.state

        for idx, console in enumerate(vm['consoles']):
            if console['type'] == 'pty':
                self.context.consoles.add(TtyConsole('tty%s'% idx, console['pty']))
            if console['type'] == 'openvz':
                self.context.consoles.add(OpenVzConsole('tty%s'% idx, console['cid']))
            if console['type'] == 'vnc':
                self.context.consoles.add(VncConsole(self.context.__parent__.__parent__.hostname, int(console['port'])))

        # networks

        self.context.interfaces = NetworkInterfaces()
        for interface in vm['interfaces']:
            iface = NetworkInterface(interface['name'], None, interface['mac'], 'active')
            if interface.has_key('ipv4_address'):
                iface.ipv4_address = interface['ipv4_address']
            self.context.interfaces.add(iface)

    @defer.inlineCallbacks
    def sync_hw(self):
        if not IFuncInstalled.providedBy(self.context):
            return

        info = yield IGetComputeInfo(self.context).run()
        self._sync_hw(info)

    @db.transact
    def _sync_hw(self, info):
        if IVirtualCompute.providedBy(self.context):
            self.context.cpu_info = self.context.__parent__.__parent__.cpu_info
        else:
            self.context.cpu_info = unicode(info['cpuModel'])

        self.context.architecture = (unicode(info['platform']), u'linux', self.distro(info))
        self.context.kernel = unicode(info['kernelVersion'])

    def distro(self, info):
        return unicode(info['os'].split()[0])


class InfoAction(Action):
    """This is a temporary command used to fetch realtime info"""
    context(IVirtualCompute)

    action('info')

    @defer.inlineCallbacks
    def execute(self, cmd, args):
        submitter = IVirtualizationContainerSubmitter(self.context.__parent__)
        try:
            # TODO: not efficient but for now it's not important to add an ad-hoc func method for this.
            for vm in (yield submitter.submit(IListVMS)):
                if vm['uuid'] == self.context.__name__:
                    max_key_len = max(len(key) for key in vm)
                    for key, value in vm.items():
                        cmd.write("%s %s\n" % ((key + ':').ljust(max_key_len), value))
        except Exception as e:
            cmd.write("%s\n" % (": ".join(msg for msg in e.args if not msg.startswith('  File "/'))))


class ComputeAction(Action):
    """Common code for virtual compute actions."""
    context(IVirtualCompute)
    baseclass()

    @defer.inlineCallbacks
    def execute(self, cmd, args):
        action_name = getattr(self, 'action_name', self._name + "ing")

        cmd.write("%s %s\n" % (action_name, self.context.__name__))
        submitter = IVirtualizationContainerSubmitter(self.context.__parent__)
        try:
            yield submitter.submit(self.job, self.context.__name__)
        except Exception as e:
            cmd.write("%s\n" % (": ".join(msg for msg in e.args if not msg.startswith('  File "/'))))


class StartComputeAction(ComputeAction):
    action('start')

    job = IStartVM


class ShutdownComputeAction(ComputeAction):
    action('shutdown')

    action_name = "shutting down"
    job = IShutdownVM


class DestroyComputeAction(ComputeAction):
    action('destroy')

    job = IDestroyVM


class SuspendComputeAction(ComputeAction):
    action('suspend')

    job = ISuspendVM


class ResumeAction(ComputeAction):
    action('resume')

    action_name = 'resuming'
    job = IResumeVM


class RebootAction(ComputeAction):
    action('reboot')

    job = IRebootVM


@subscribe(ICompute, IModelModifiedEvent)
@defer.inlineCallbacks
def handle_compute_state_change_request(compute, event):
    if not event.modified.get('state', None):
        return

    submitter = IVirtualizationContainerSubmitter(compute.__parent__)

    if event.original['state'] == 'inactive' and event.modified['state'] == 'active':
        action = IStartVM
    elif event.original['state'] == 'suspended' and event.modified['state'] == 'active':
        action = IResumeVM
    elif event.original['state'] == 'active' and event.modified['state'] == 'inactive':
        action = IShutdownVM
    elif event.original['state'] == 'active' and event.modified['state'] == 'suspended':
        action = ISuspendVM
    else:
        return

    try:
        yield submitter.submit(action, compute.__name__)
    except Exception as e:
        compute.effective_state = event.original['state']
        raise e
    compute.effective_state = event.modified['state']
