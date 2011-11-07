from __future__ import absolute_import

from grokcore.component import context, subscribe, baseclass
from twisted.internet import defer

from .virtualizationcontainer import IVirtualizationContainerSubmitter
from opennode.oms.backend.operation import IStartVM, IShutdownVM, IDestroyVM, ISuspendVM, IResumeVM, IListVMS, IRebootVM
from opennode.oms.model.form import IModelModifiedEvent
from opennode.oms.model.model.actions import Action, action
from opennode.oms.model.model.compute import ICompute, IVirtualCompute
from opennode.oms.model.model.console import Consoles, TtyConsole, SshConsole, VncConsole
from opennode.oms.model.model.network import NetworkInterfaces, NetworkInterface
from opennode.oms.model.model.symlink import Symlink
from opennode.oms.zodb import db


class SyncAction(Action):
    """Force compute sync"""
    context(IVirtualCompute)

    action('sync')

    @defer.inlineCallbacks
    def execute(self, cmd, args):
        submitter = IVirtualizationContainerSubmitter(self.context.__parent__)
        try:
            # TODO: not efficient but for now it's not important to add an ad-hoc func method for this.
            for vm in (yield submitter.submit(IListVMS)):
                if vm['uuid'] == self.context.__name__:
                    yield self._sync(cmd, vm)
        except Exception as e:
            cmd.write("%s\n" % (": ".join(msg for msg in e.args if not msg.startswith('  File "/'))))

    @db.transact
    def _sync(self, cmd, vm):
        cmd.write("syncing %s\n" % self.context)
        self.context.state = unicode(vm['state'])
        self.context.effective_state = self.context.state
        self.context.consoles = Consoles()

        for idx, console in enumerate(vm['consoles']):
            if console['type'] == 'pty':
                self.context.consoles.add(TtyConsole('tty%s'% idx, console['pty']))
            if console['type'] == 'vnc':
                self.context.consoles.add(VncConsole(self.context.hostname, int(console['port'])))

        ssh_console = SshConsole('ssh', 'root', self.context.hostname, 22)
        self.context.consoles.add(ssh_console)
        self.context.consoles.add(Symlink('default', ssh_console))

        # networks

        self.context.interfaces = NetworkInterfaces()
        for interface in vm['interfaces']:
            self.context.interfaces.add(NetworkInterface(interface['name'], None, interface['mac'], 'active'))


class FakeConsoles(Action):
    context(ICompute)

    action('fake_consoles')

    def execute(self, cmd, args):
        self.context.consoles = Consoles()

        ssh_console = SshConsole('ssh', 'root', self.context.hostname, 22)
        self.context.consoles.add(ssh_console)
        self.context.consoles.add(Symlink('default', ssh_console))


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

