from __future__ import absolute_import

from zope import schema
from zope.interface import Interface, implements

from .base import Model, Container


class ICompute(Interface):
    architecture = schema.TextLine(title=u"Architecture", min_length=1)
    hostname = schema.TextLine(title=u"Host name", min_length=1)
    speed = schema.Int(title=u"CPU Speed", description=u"CPU Speed in MHz")
    memory = schema.Int(title=u"RAM Size", description=u"RAM size in megabytes")
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
