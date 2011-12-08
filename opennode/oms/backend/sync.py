from twisted.internet import defer
from uuid import uuid5, NAMESPACE_DNS
from zope.component import provideSubscriptionAdapter
from zope.interface import implements

from opennode.oms.model.model.proc import IProcess, Proc, DaemonProcess
from opennode.oms.model.model.compute import ICompute
from opennode.oms.util import subscription_factory, async_sleep
from opennode.oms.zodb import db
from opennode.oms.model.model.symlink import follow_symlinks
from opennode.oms.model.model.compute import Compute
from opennode.oms.endpoint.ssh.detached import DetachedProtocol
from opennode.oms.backend.operation import IGetSignedCertificateNames, IFuncMinion, IFuncInstalled


class CertmasterMinion(object):
    implements(IFuncInstalled, IFuncMinion)

    def hostname(self):
        return 'localhost'


class SyncDaemonProcess(DaemonProcess):
    implements(IProcess)

    __name__ = "sync"

    @defer.inlineCallbacks
    def run(self):
        while True:
            try:
                if not self.paused:
                    yield self.sync()
            except Exception:
                import traceback
                traceback.print_exc()
                pass

            yield async_sleep(10)

    @defer.inlineCallbacks
    def sync(self):
        print "[sync] syncing"

        @db.transact
        def ensure_machine(host):
            machines = db.get_root()['oms_root'].machines
            existing_machine = follow_symlinks(machines['by-name'][host])
            if not existing_machine:
                machine = Compute(unicode(host), u'active')
                machine.__name__ = str(uuid5(NAMESPACE_DNS, host))
                machines.add(machine)

        @defer.inlineCallbacks
        def import_machines():
            for host in (yield IGetSignedCertificateNames(CertmasterMinion()).run()):
                yield ensure_machine(host)

        yield import_machines()

        @db.transact
        def get_machines():
            res = []

            oms_root = db.get_root()['oms_root']
            for i in [follow_symlinks(i) for i in oms_root.machines.listcontent()]:
                res.append(i)

            return res

        from opennode.oms.backend.func.compute import SyncAction
        for i in (yield get_machines()):
            if ICompute.providedBy(i):
                action = SyncAction(i)
                action.execute(DetachedProtocol(), object())

        print "[sync] synced"

provideSubscriptionAdapter(subscription_factory(SyncDaemonProcess), adapts=(Proc,))
