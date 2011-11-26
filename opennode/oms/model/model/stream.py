from __future__ import absolute_import

from .base import ReadonlyContainer


class StreamSubscriber(ReadonlyContainer):
    __name__ = 'stream'

    _items = {}
