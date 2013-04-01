from __future__ import absolute_import

import time
from collections import OrderedDict

from grokcore.component import querySubscriptions, Adapter, context, subscribe, baseclass
from twisted.python import log
from zope import schema
from zope.component import provideSubscriptionAdapter
from zope.interface import Interface, implements, alsoProvides

from .base import ReadonlyContainer
from .actions import ActionsContainerExtension, Action, action
from opennode.oms.util import Singleton
from opennode.oms.config import get_config
from opennode.oms.core import IAfterApplicationInitializedEvent


class ITask(Interface):
    """Executable command object."""
    cmdline = schema.TextLine(title=u"command line", description=u"Command line", readonly=True, required=False)
    uptime = schema.Int(title=u"uptime", description=u"Task uptime in seconds", readonly=True, required=False)
    ptid = schema.TextLine(title=u"parent task", description=u"Parent task", readonly=True, required=False)
    stdout = schema.TextLine(title=u"stdout", description=u"Standard output", readonly=True, required=False)

    def signal(name):
        """Process a signal"""


class ISuspendableTask(Interface):
    """A task which can be suspendedD."""

    def stop():
        pass

    def cont():
        pass


class IProcess(Interface):
    def run():
        """Returns a deferred representing the background process execution"""

    def signal_handler(name):
        """Process a signal"""


class DaemonProcess(object):
    def __init__(self):
        config = get_config()
        self.paused = not config.getboolean('daemons', self.__name__, True)

    def signal_handler(self, name):
        if name == 'STOP':
            log.msg("Stopping %s" % self.__name__, system='proc')
            self.paused = True
        elif name == 'CONT':
            log.msg("Continuing %s" % self.__name__, system='proc')
            self.paused = False


class IProcessStateRenderer(Interface):
    def __str__():
        pass


class DaemonStateRenderer(Adapter):
    implements(IProcessStateRenderer)
    context(DaemonProcess)

    def __str__(self):
        return "[%s%s]" % (self.context.__name__, ': paused' if self.context.paused else '')


class Task(ReadonlyContainer):
    implements(ITask)

    def __init__(self, name, parent, subject, deferred, cmdline, ptid,
                 signal_handler=None, principal=None, write_buffer=None):
        self.__name__ = name
        self.__parent__ = parent
        self.subject = subject
        self.deferred = deferred
        self.cmdline = cmdline
        self.timestamp = time.time()
        self.ptid = ptid
        self.signal_handler = signal_handler
        self.principal = principal
        self.write_buffer = write_buffer

        # XXX: Workaround to handle ON-425
        # Refactor with adapters handling each specific signal
        if self.signal_handler:
            alsoProvides(self, ISuspendableTask)

    @property
    def uptime(self):
        return time.time() - self.timestamp

    @property
    def nicknames(self):
        return [self.cmdline, ]

    @property
    def stdout(self):
        return self.write_buffer

    def signal(self, name):
        if self.signal_handler:
            self.signal_handler(name)


class Proc(ReadonlyContainer):
    __metaclass__ = Singleton

    __contains__ = ITask
    __name__ = 'proc'

    def __init__(self):
        super(Proc, self).__init__()
        # represents the init process, just for fun.
        self.tasks = OrderedDict({'1': Task('1', self, self, None, '/bin/init', '0')})

        self.dead_tasks = OrderedDict()
        self.next_id = 1

    def start_daemons(self):
        for i in querySubscriptions(self, IProcess):
            self.spawn(i)

    def spawn(self, process):
        self._register(process.run(), process, IProcessStateRenderer(process),
                       signal_handler=process.signal_handler)

    def __str__(self):
        return 'Tasks'

    def content(self):
        res = dict(self.tasks)
        res['completed'] = CompletedProc(self, self.dead_tasks)
        return res

    @classmethod
    def register(cls, deferred, subject, cmdline=None, ptid='1', principal=None, write_buffer=None):
        pid = Proc()._register(deferred, subject, cmdline, ptid, principal=principal,
                               write_buffer=write_buffer)
        log.msg('Registered as process %s: %s' % (pid, cmdline), system='proc')
        return pid

    def _register(self, deferred, subject, cmdline,
                  ptid='1', signal_handler=None, principal=None, write_buffer=None):
        self.next_id += 1
        new_id = str(self.next_id)
        self.tasks[new_id] = Task(new_id, self, subject, deferred, cmdline, ptid, signal_handler,
                                  principal, write_buffer)
        if deferred:
            deferred.addBoth(self._unregister, new_id)

        return new_id

    @classmethod
    def unregister(cls, id_):
        self = Proc()
        self.dead_tasks[id_] = self.tasks[id_]
        del self.tasks[id_]
        log.msg('Unregistered process %s: %s' % (id_, self.dead_tasks[id_].cmdline), system='proc')

    @classmethod
    def _unregister(cls, res, id_):
        cls.unregister(id_)
        return res


class CompletedProc(ReadonlyContainer):
    __name__ = 'completed'

    def __init__(self, parent, tasks):
        self.__parent__ = parent
        self.tasks = tasks

    def content(self):
        return self.tasks


class SignalAction(Action):
    """Send a given signal"""
    baseclass()

    def execute(self, cmd, args):
        from opennode.oms.zodb import db

        @db.ro_transact
        def execute():
            self.context.signal(self.__signal__)
        execute()


class StopTaskAction(SignalAction):
    """Send STOP signal"""
    context(ISuspendableTask)
    action('stop')

    __signal__ = 'STOP'


class ContinueTaskAction(SignalAction):
    """Send CONT signal"""

    context(ISuspendableTask)
    action('continue')

    __signal__ = 'CONT'


class TerminateTaskAction(SignalAction):
    """Send TERM signal"""

    context(ITask)
    action('terminate')

    __signal__ = 'TERM'


provideSubscriptionAdapter(ActionsContainerExtension, adapts=(Task, ))


@subscribe(IAfterApplicationInitializedEvent)
def start_daemons(event):
    try:
        Proc().start_daemons()
    except Exception as e:
        log.msg("Got exception while starting daemons", system='proc')
        if get_config().get_boolean('debug', 'print_exceptions'):
            log.err(e, system='proc')
