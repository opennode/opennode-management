import time

from twisted.internet import defer
from zope.component import provideSubscriptionAdapter
from zope.interface import implements

from opennode.oms.config import get_config
from opennode.oms.model.model.proc import IProcess, Proc, DaemonProcess
from opennode.oms.util import subscription_factory, async_sleep
from opennode.oms.zodb import db


class PackDaemonProcess(DaemonProcess):
    implements(IProcess)

    __name__ = "db_pack"

    def __init__(self):
        super(PackDaemonProcess, self).__init__()

        config = get_config()
        self.interval = config.getint('db', 'pack_interval')

    @defer.inlineCallbacks
    def run(self):
        while True:
            try:
                if not self.paused:
                    yield self.pack()
            except Exception:
                import traceback
                traceback.print_exc()
                pass

            yield async_sleep(self.interval)

    @db.ro_transact
    def pack(self):
        storage_type = get_config().get('db', 'storage_type')

        if storage_type == 'zeo':
            print "[db_pack] zeo pack not implemented yet, please setup cron to run bin/zeopack -u db/socket"
        elif storage_type == 'embedded':
            d = db.get_db()
            d.pack(time.time())


provideSubscriptionAdapter(subscription_factory(PackDaemonProcess), adapts=(Proc,))
