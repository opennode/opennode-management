from __future__ import absolute_import

from .base import ReadonlyContainer
from .bin import Bin
from .log import Log
from .proc import Proc
from .search import SearchContainer
from .stream import StreamSubscriber
from .plugins import Plugins


class OmsRoot(ReadonlyContainer):
    """The root of the OMS DB.

    This model is the root of the object hierarchy.

    Absolute object traversals start from this object.

    """

    __name__ = ''

    _items = property(lambda self: {
        'search': self.search,
        'bin': self.bin,
        'proc': self.proc,
        'plugins': self.plugins,
        'log': self.log,
        'stream': self.stream,
    })

    def __init__(self):
        pass

    @property
    def bin(self):
        bin = Bin()
        bin.__parent__ = self
        return bin

    @property
    def proc(self):
        proc = Proc()
        proc.__parent__ = self
        return proc

    @property
    def log(self):
        if not getattr(self, '_log', None):
            self._log = Log()
            self._log.__parent__ = self
        return self._log

    @property
    def search(self):
        if not getattr(self, '_search', None):
            self._search = SearchContainer()
            self._search.__parent__ = self
        return self._search

    @property
    def stream(self):
        res = StreamSubscriber()
        res.__parent__ = self
        return res

    @property
    def plugins(self):
        res = Plugins()
        res.__parent__ = self
        return res

    def __str__(self):
        return 'OMS root'
