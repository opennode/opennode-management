from __future__ import absolute_import

from zope.interface import Interface, implements

from .base import Container
from .compute import ICompute, IInCompute


class IHangar(Interface):
    pass


class Hangar(Container):
    implements(IHangar, IInCompute)

    __contains__ = ICompute

    def __init__(self):
        super(Hangar, self).__init__()

        self.__name__ = 'hangar'

    def __str__(self):
        return self.__name__
