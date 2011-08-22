from __future__ import absolute_import

from zope import schema
from zope.component import provideSubscriptionAdapter
from zope.interface import Interface, implements

from .base import Model, Container
from .byname import ByNameContainerExtension


class ICompute(Interface):
    architecture = schema.Choice(title=u"Architecture", values=(u'linux', u'win32', u'darwin', u'bsd', u'solaris'))
    hostname = schema.TextLine(title=u"Host name", min_length=3)
    speed = schema.Int(title=u"CPU Speed", description=u"CPU Speed in MHz")
    memory = schema.Int(title=u"RAM Size", description=u"RAM size in MB")
    state = schema.Choice(title=u"State", values=(u'active', u'inactive', u'standby'))


class Compute(Model):
    implements(ICompute)

    def __init__(self, architecture, hostname, speed, memory, state, template=None):
        self.architecture = architecture
        self.hostname = hostname
        self.speed = speed
        self.memory = memory
        self.state = state
        self.template = template

    def display_name(self):
        return self.hostname

    @property
    def nicknames(self):
        """Returns all the nicknames of this Compute instance.

        Nicknames can be used to traverse to this object using
        alternative, potentially more convenient and/more memorable,
        names.

        """
        return [
            'c%s' % self.__name__,
            'compute%s' % self.__name__,
            self.hostname,
        ]

    def __str__(self):
        return 'compute%s' % self.__name__


class Computes(Container):
    __contains__ = Compute

    def __str__(self):
        return 'Compute list'


provideSubscriptionAdapter(ByNameContainerExtension, adapts=(Computes, ))
