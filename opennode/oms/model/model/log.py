from __future__ import absolute_import

from .base import ReadonlyContainer, IContainer

class ILogContainer(IContainer):
    """A logging container"""


class Log(ReadonlyContainer):
    __contains__ = ILogContainer
    __name__ = 'log'

    _items = property(lambda self: {
        'news': self.news,
        })

    @property
    def news(self):
        from .news import News

        if not getattr(self, '_news', None):
            self._news = News()
            self._news.__parent__ = self
        return self._news
