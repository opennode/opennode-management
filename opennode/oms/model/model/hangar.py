from __future__ import absolute_import

from zope import schema
from zope.interface import Interface, implements

from .base import Model, Container
from .compute import VirtualCompute, IInPhysicalCompute


class IHangar(Interface):
    pass


class Hangar(Container):
    implements(IHangar, IInPhysicalCompute)

    __contains__ = VirtualCompute

    def __init__(self):
        super(Hangar, self).__init__()

        self.__name__ = 'hangar'

    def __str__(self):
        return self.__name__
