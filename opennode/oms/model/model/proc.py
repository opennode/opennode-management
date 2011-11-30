from __future__ import absolute_import

import time
from collections import OrderedDict

from grokcore.component import querySubscriptions
from zope import schema
from zope.interface import Interface, implements

from .base import Model, ReadonlyContainer
from opennode.oms.util import Singleton
from opennode.oms.config import get_config


class ITask(Interface):
    """Executable command object."""
    cmdline = schema.TextLine(title=u"command line", description=u"Command line", readonly=True, required=False)
    uptime = schema.Int(title=u"uptime", description=u"Task uptime in seconds", readonly=True, required=False)
    ptid = schema.TextLine(title=u"parent task", description=u"Parent task", readonly=True, required=False)

    def signal(name):
        """Process a signal"""


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
            print "Stopping %s" % self.__name__
            self.paused = True
        elif name == 'CONT':
            print "Continuing %s" % self.__name__
            self.paused = False


class Task(Model):
    implements(ITask)

    def __init__(self, name, parent, deferred, cmdline, ptid, signal_handler=None):
        self.__name__ = name
        self.__parent__ = parent
        self.deferred = deferred
        self.cmdline = cmdline
        self.timestamp = time.time()
        self.ptid = ptid
        self.signal_handler = signal_handler

    @property
    def uptime(self):
        return time.time() - self.timestamp

    @property
    def nicknames(self):
        return [self.cmdline, ]

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
        self.tasks = OrderedDict({'1': Task('1', self, None, '/bin/init', '0')})

        self.dead_tasks = OrderedDict()
        self.next_id = 1

        for i in querySubscriptions(self, IProcess):
            self.spawn(i)

    def spawn(self, process):
        self._register(process.run(), '[%s]' % process.__name__, signal_handler=process.signal_handler)

    def __str__(self):
        return 'Tasks'

    def content(self):
        res = dict(self.tasks)
        res['completed'] = CompletedProc(self, self.dead_tasks)
        return res

    @classmethod
    def register(cls, deferred, cmdline=None, ptid='1'):
        return Proc()._register(deferred, cmdline, ptid)

    def _register(self, deferred, cmdline=None, ptid='1', signal_handler=None):

        self.next_id += 1
        new_id = str(self.next_id)

        self.tasks[new_id] = Task(new_id, self, deferred, cmdline, ptid, signal_handler)

        if deferred:
            deferred.addBoth(self._unregister, new_id)

        return new_id

    @classmethod
    def unregister(cls, id):
        self = Proc()
        self.dead_tasks[id] = self.tasks[id]
        del self.tasks[id]

    @classmethod
    def _unregister(cls, res, id):
        cls.unregister(id)
        return res




class CompletedProc(ReadonlyContainer):
    __name__ = 'completed'

    def __init__(self, parent, tasks):
        self.__parent__ = parent
        self.tasks = tasks

    def content(self):
        return self.tasks
