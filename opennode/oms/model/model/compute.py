from __future__ import absolute_import

from zope import schema
from zope.interface import Interface, implements

from .base import Model, IContainer, Container, AddingContainer


class ICompute(Interface):
    architecture = schema.Choice(title=u"Architecture", values=(u'linux', u'win32', u'darwin', u'bsd', u'solaris'))
    hostname = schema.TextLine(title=u"Host name", min_length=3)
    speed = schema.Int(title=u"CPU Speed", description=u"CPU Speed in MHz")
    memory = schema.Int(title=u"RAM Size", description=u"RAM size in MB")
    state = schema.Choice(title=u"State", values=(u'active', u'inactive', u'standby'))


class Compute(Model):
    """Abstract class representing compute nodes."""

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
        return [self.hostname, ]

    def __str__(self):
        return 'compute%s' % self.__name__


class VirtualCompute(Compute):
    """Represents a virtual machine."""

    implements(ICompute)


class IInPhysicalCompute(Interface):
    """Implementors of this interface can be contained in a `PhysicalCompute` container."""


class PhysicalCompute(Container, Compute):
    """Represents a physical machine which can optionally contain a `VirtualizationContainer`."""

    implements(ICompute)

    __contains__ = IInPhysicalCompute


class Computes(AddingContainer):
    __contains__ = ICompute

    def __str__(self):
        return 'Compute list'

    @property
    def _items(self):
        # break an import cycle
        from opennode.oms.zodb import db
        machines = db.get_root()['oms_root'].machines

        computes = {}

        def collect(container):
            for item in container.listcontent():
                if ICompute.providedBy(item):
                    computes[item.__name__] = item
                if IContainer.providedBy(item):
                    collect(item)

        collect(machines)
        return computes

    def add(self, item):
        # break an import cycle
        from opennode.oms.zodb import db
        machines = db.get_root()['oms_root'].machines

        if isinstance(item, PhysicalCompute):
            machines.add(item)
        elif isinstance(item, VirtualCompute):
            machines.hangar.add(item)
