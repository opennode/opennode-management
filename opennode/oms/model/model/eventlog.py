from __future__ import absolute_import

from grokcore.component import context
from zope import schema
from zope.interface import implements, Interface

from .base import Container, IContainer, ContainerInjector, Model
from .root import OmsRoot


class IUserLogger(Interface):

    def log(msg, *args, **kwargs):
        """ log event """


class IUserEventLogContainer(IContainer):
    """An event log container"""
    sizelimit = schema.Int(title=u'Size limit',
                           description=u'The number of events this container is allowed to hold')

    cur_index = schema.Int(title=u'Current index')

class IUserEvent(Interface):
    timestamp = schema.Float(title=u'Timestamp', description=u'Timestamp of event recording')
    message = schema.TextLine(title=u'Message')
    levelname = schema.TextLine(title=u'Log level')
    thread = schema.Int(title=u'Thread ID')
    threadName = schema.TextLine(title=u'Thread name')


class UserEvent(Model):
    implements(IUserEvent)
    _rawevent = None

    def __init__(self, event, index):
        self._rawevent = event
        self._index = index
        self.__name__ = '%s' % (self._index)

    @property
    def thread(self):
        return self._rawevent.thread

    @property
    def threadName(self):
        return self._rawevent.threadName

    @property
    def timestamp(self):
        return self._rawevent.asctime

    @property
    def levelname(self):
        return self._rawevent.levelname

    @property
    def message(self):
        return self._rawevent.getMessage()


class UserEventLog(Container):
    implements(IUserEventLogContainer)
    __contains__ = IUserEvent
    __name__ = 'unknown'
    sizelimit = None

    def __init__(self, username, sizelimit=None):
        self.__name__ = username
        self.sizelimit = None
        self.cur_index = 0

    def add(self, rawevent):
        if rawevent.username != self.__name__:
            return

        if self.sizelimit is not None and self.sizelimit > 0 and len(self._items) >= self.sizelimit:
            del self._items[min(self._items.keys())]

        super(UserEventLog, self).add(UserEvent(rawevent, self.cur_index))
        self.cur_index += 1


class EventLog(Container):
    __contains__ = IUserEventLogContainer
    __name__ = 'eventlog'


class EventLogRootInjector(ContainerInjector):
    context(OmsRoot)
    __class__ = EventLog
