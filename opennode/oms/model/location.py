"""Provides the ILocation aspect to OMS models."""

from zope.component import adapts, provideAdapter
from zope.interface import Interface, implements

from opennode.oms.model.model import IModel, OmsRoot


__all__ = ['ILocation']


class ILocation(Interface):
    """Information about the location of an object."""

    def get_path():
        """Returns the path to the object starting from the root as a list of object names."""

    def get_url():
        """Returns the canonical URL of the object object without the URI scheme and domain parts."""


class ModelLocation(object):
    implements(ILocation)
    adapts(IModel)

    def __init__(self, context):
        self.context = context

    def get_path(self):
        return ILocation(self.context.__parent__).get_path() + [self.context.__name__]

    def get_url(self):
        return '%s%s/' % (ILocation(self.context.__parent__).get_url(), self.context.__name__)


class OmsRootLocation(object):
    implements(ILocation)
    adapts(OmsRoot)

    def __init__(self, context):
        pass

    def get_path(self):
        return ['']

    def get_url(self):
        return '/'


provideAdapter(ModelLocation)
provideAdapter(OmsRootLocation)
