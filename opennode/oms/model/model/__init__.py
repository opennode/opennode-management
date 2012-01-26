from __future__ import absolute_import

from .root import OmsRoot
from .news import NewsItem

__all__ = [OmsRoot]


creatable_models = dict((cls.__name__.lower(), cls)
                        for cls in [NewsItem])
