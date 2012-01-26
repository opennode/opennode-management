from __future__ import absolute_import

import time
from datetime import datetime

from zope import schema
from zope.interface import Interface, implements

from .base import Model, Container
from .log import ILogContainer

from opennode.oms.security.directives import permissions


class INewsItem(Interface):
    """A news item in the activity stream"""
    message = schema.TextLine(title=u"message", description=u"message")
    timestamp = schema.Float(title=u"uptime", description=u"Task uptime in seconds", readonly=True, required=False)


class NewsItem(Model):
    implements(INewsItem)
    permissions(dict(message=('read', 'modify'),
                     timestamp='read',
                     ))

    def __init__(self, message):
        self.message = message
        self.timestamp = time.time()

    @property
    def nicknames(self):
        return [str(datetime.fromtimestamp(self.timestamp)), self.message]


class News(Container):
    implements(ILogContainer)

    __contains__ = INewsItem
    __name__ = 'news'
