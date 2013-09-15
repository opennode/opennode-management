import gc
import logging
from pprint import pformat

from pympler import summary
from pympler import tracker
from pympler import muppy
from pympler.util import stringutils
from twisted.python import log
from twisted.internet import defer
from zope.component import provideSubscriptionAdapter
from zope.interface import implements

from opennode.oms.config import get_config
from opennode.oms.endpoint.ssh.cmd.security import require_admins_only
from opennode.oms.model.model.proc import IProcess, DaemonProcess, Proc
from opennode.oms.util import subscription_factory, async_sleep
from opennode.oms.zodb import db


logger = logging.getLogger(__name__)


class MemoryProfilerDaemonProcess(DaemonProcess):
    implements(IProcess)
    __name__ = 'memory-profiler'

    def __init__(self):
        super(MemoryProfilerDaemonProcess, self).__init__()
        config = get_config()
        self.enabled = config.getboolean('daemon', 'memory-profiler', False)
        self.interval = config.getint('debug', 'memory_profiler_interval', 60)
        self.track = config.getint('debug', 'memory_profiler_track_changes', 0)
        self.verbose = config.getint('debug', 'memory_profiler_verbose', 0)
        self.summary_tracker = tracker.SummaryTracker()
         

    @defer.inlineCallbacks
    def run(self):
        if self.enabled and self.track:
            yield self.collect_and_dump()

        while True:
            try:
                if self.enabled and not self.paused:
                    if self.track:
                        yield self.track_changes()
                    else:
                        yield self.collect_and_dump()
                        if self.verbose:
                            yield self.collect_and_dump_garbage()
                            yield self.collect_and_dump_root()
            except Exception:
                log.err(system=self.__name__)

            yield async_sleep(self.interval)

    def collect_and_dump_garbage(self):
        logger.info('Uncollectable garbage list follows')
        objects = gc.garbage
        logger.info(pformat(objects))
        return defer.succeed(None)

    def collect_and_dump_root(self):
        log.msg('Profiling memory for OmsRoot objects...', system=self.__name__)
        try:
            import inspect
            from sys import getsizeof
            from BTrees.OOBTree import OOBucket
            from ZEO.Exceptions import ClientDisconnected
            from opennode.oms.model.model.root import OmsRoot

            data = []
            all_objects = muppy.get_objects()
            roots = muppy.filter(all_objects, Type=OmsRoot)
            logger.info('Root profile follows (%s rows)' % len(roots))

            gc.collect()

            for ue in roots:
                referrers = []
                for ref in gc.get_referrers(ue):
                    try:
                        if inspect.isframe(ref):
                            continue  # local object ref
                        elif isinstance(ref, list):
                            referrers.append('list len=%s id=%x' % (len(ref), id(ref)))
                        elif isinstance(ref, OOBucket):
                            referrers.append('OOBucket len=%s id=%x' % (len(ref), id(ref)))
                        else:
                            sref = repr(ref)
                            referrers.append(sref)
                    except ClientDisconnected:
                        referrers.append('ClientDisconnected')

                data.append((referrers, str(ue), repr(ue), str(getsizeof(ue))))

            rrows = [('object', 'raw', 'size', 'referrers')] + data
            rows = _format_table(rrows)
            for row in rows:
                logger.info(row)

            log.msg('Profiling Omsroot memory done', system=self.__name__)
            del all_objects
            gc.collect()
            return defer.succeed(None)
        except Exception, e:
            import traceback
            logger.error(traceback.format_exc(e))
            return defer.fail(None)

    def collect_and_dump(self):
        log.msg('Profiling memory...', system=self.__name__)
        logger.info('Full profile follows')
        summary_ = self.summary_tracker.create_summary()
        for line in format_(summary_):
            logger.info(line)
        log.msg('Profiling memory done', system=self.__name__)
        return defer.succeed(None)

    def track_changes(self):
        log.msg('Profiling memory (tracking changes)...', system=self.__name__)
        logger.info('Change summary follows')
        summary_ = self.summary_tracker.diff()
        for line in format_(summary_):
            logger.info(line)
        log.msg('Profiling memory (tracking changes) done', system=self.__name__)
        return defer.succeed(None)


provideSubscriptionAdapter(subscription_factory(MemoryProfilerDaemonProcess), adapts=(Proc,))


def format_(rows, limit=15, sort='size', order='descending'):
    """Format the rows as a summary.

    Keyword arguments:
    limit -- the maximum number of elements to be listed
    sort  -- sort elements by 'size', 'type', or '#'
    order -- sort 'ascending' or 'descending'

    Heavily based on pympler.summary.print_
    """
    localrows = []
    for row in rows:
        localrows.append(list(row))
    # input validation
    sortby = ['type', '#', 'size']
    if sort not in sortby:
        raise ValueError("invalid sort, should be one of" + str(sortby))
    orders = ['ascending', 'descending']
    if order not in orders:
        raise ValueError("invalid order, should be one of" + str(orders))
    # sort rows
    if sortby.index(sort) == 0:
        if order == "ascending":
            localrows.sort(key=lambda x: summary._repr(x[0]))
        elif order == "descending":
            localrows.sort(key=lambda x: summary._repr(x[0]), reverse=True)
    else:
        if order == "ascending":
            localrows.sort(key=lambda x: x[sortby.index(sort)])
        elif order == "descending":
            localrows.sort(key=lambda x: x[sortby.index(sort)], reverse=True)
    # limit rows
    localrows = localrows[0:limit]
    for row in localrows:
        row[2] = stringutils.pp(row[2])
    # print rows
    localrows.insert(0, ["types", "# objects", "total size"])
    return _format_table(localrows)


def _format_table(rows, header=True):
    """Format a list of lists as a pretty table.

    Keyword arguments:
    header -- if True the first row is treated as a table header

    inspired by http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/267662
    """
    border = "="
    # vertical delimiter
    vdelim = " | "
    # padding nr. of spaces are left around the longest element in the
    # column
    padding = 1
    # may be left,center,right
    justify = 'right'
    justify = {'left': str.ljust,
               'center': str.center,
               'right': str.rjust}[justify.lower()]
    # calculate column widths (longest item in each col
    # plus "padding" nr of spaces on both sides)
    cols = zip(*rows)
    colWidths = [max([len(str(item)) + 2 * padding for item in col])
                 for col in cols]
    borderline = vdelim.join([w * border for w in colWidths])

    out_rows = []
    for row in rows:
        out_rows.append(vdelim.join([justify(str(item), width)
                                     for (item, width) in zip(row, colWidths)]))
        if header:
            out_rows.append(borderline)
            header = False
    return out_rows


from grokcore.component import implements

from opennode.oms.endpoint.ssh.cmd.base import Cmd
from opennode.oms.endpoint.ssh.cmdline import ICmdArgumentsSyntax
from opennode.oms.endpoint.ssh.cmdline import VirtualConsoleArgumentParser
from opennode.oms.endpoint.ssh.cmd.directives import command


class CommandInterfaceWriter(logging.Handler):
    """ """

    storage = {}

    def __init__(self, cmd):
        logging.Handler.__init__(self)
        self.cmd = cmd

    def emit(self, record):
        self.cmd.write(self.format(record))
        self.cmd.write('\n')


def find_daemon_in_proc(daemontype):
    for pid, process in Proc().tasks.iteritems():
        if type(process.subject) is daemontype:
            return process.subject


class MemoryProfileCmd(Cmd):
    implements(ICmdArgumentsSyntax)
    command('memoryprofile')

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('-t', action='store_true', help='Force tracking changes')
        parser.add_argument('-s', help='Show details for particular types')
        parser.add_argument('-d', action='store_true', help='Step into debugger')
        parser.add_argument('-b', action='store_true', help='Step into debugger in DB thread')
        return parser

    @require_admins_only
    @defer.inlineCallbacks
    def execute(self, args):

        if args.d:
            import ipdb
            ipdb.set_trace()
            return

        if args.b:
            @db.ro_transact
            def get_db_object(path):
                import ipdb
                ipdb.set_trace()
                return self.traverse(path)
            yield get_db_object('/')
            return

        if args.t:
            mpdaemon = find_daemon_in_proc(MemoryProfilerDaemonProcess)
            oldtrack = mpdaemon.track
            mpdaemon.track = True

        handler = CommandInterfaceWriter(self)
        logger.addHandler(handler)

        def keystrokeReceived(keyID, mod):
            logger.removeHandler(handler)
            if args.t:
                mpdaemon.track = oldtrack
            r = self.protocol._orig_keystrokeReceived(keyID, mod)
            self.protocol.keystrokeReceived = self.protocol._orig_keystrokeReceived
            return r

        self.protocol._orig_keystrokeReceived = self.protocol.keystrokeReceived
        self.protocol.keystrokeReceived = keystrokeReceived

        try:
            while True:
                yield async_sleep(1)
        finally:
            logger.removeHandler(handler)
            if args.t:
                mpdaemon.track = oldtrack

            self.protocol.keystrokeReceived = self.protocol._orig_keystrokeReceived
