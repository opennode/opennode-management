from __future__ import absolute_import

from zope import schema
from zope.component import provideSubscriptionAdapter
from zope.interface import Interface, implements, alsoProvides

from .base import Model, IContainer, Container, AddingContainer, IIncomplete
from .symlink import Symlink
from .byname import ByNameContainerExtension
from opennode.oms.model.schema import Path


class ICompute(Interface):
    architecture = schema.Choice(title=u"Architecture", values=(u'linux', u'win32', u'darwin', u'bsd', u'solaris'))
    hostname = schema.TextLine(title=u"Host name", min_length=3)
    ipv4_address = schema.TextLine(title=u"IPv4 address", min_length=7, required=False)
    ipv6_address = schema.TextLine(title=u"IPv6 address", min_length=6, required=False)
    speed = schema.Int(title=u"CPU Speed", description=u"CPU Speed in MHz", readonly=True, required=False)
    memory = schema.Int(title=u"RAM Size", description=u"RAM size in MB")
    state = schema.Choice(title=u"State", values=(u'active', u'inactive', u'suspended'))
    effective_state = schema.TextLine(title=u"Effective state", readonly=True, required=False)
    template = Path(title=u"Template", required=False, base_path='/templates/by-name/')


class IInCompute(Interface):
    """Implementors of this interface can be contained in a `Compute` container."""


class IDeployed(Interface):
    """Marker interface implemented when the compute has been deployed."""


class Compute(Container):
    """A compute node."""

    implements(ICompute)

    __contains__ = IInCompute

    ipv4_address = u'0.0.0.0/32'
    ipv6_address = u'::/128'
    type = 'unknown'  # XXX: how should this be determined?
                      # and how do we differentiate for ONC physical and virtual computes?
    cpu = "Intel Xeon 12.2GHz"
    memory = 2048,
    os_release = "build 35"
    kernel = "2.6.18-238.9.1.el5.028stab089.1"
    network_usage = 1000
    speed = 2000
    diskspace = 750
    swap_size = 7777
    diskspace_rootpartition = 77.7
    diskspace_storagepartition = 77.7
    diskspace_vzpartition = 77.7
    diskspace_backuppartition = 77.7
    startup_timestamp = "2011-07-06 01:23:45"

    def __init__(self, architecture, hostname, memory, state, template=None, ipv4_address=None):
        super(Compute, self).__init__()

        self.architecture = architecture
        self.hostname = hostname
        self.memory = memory
        self.state = state
        self.template = template
        if ipv4_address:
            self.ipv4_address = ipv4_address

        if self.template:
            alsoProvides(self, IVirtualCompute)

        alsoProvides(self, IIncomplete)

    def display_name(self):
        return self.hostname.encode('utf-8')

    @property
    def nicknames(self):
        """Returns all the nicknames of this Compute instance.

        Nicknames can be used to traverse to this object using
        alternative, potentially more convenient and/more memorable,
        names.

        """
        return [self.hostname, ]

    def get_effective_state(self):
        """Since we lack schema/data upgrade scripts I have to
        resort on this tricks to cope with the fact that I have
        existing objects around in the several test dbs, and branches.

        """
        return getattr(self, '_effective_state', unicode(self.state))

    def set_effective_state(self, value):
        self._effective_state = value

    effective_state = property(get_effective_state, set_effective_state)

    def __str__(self):
        return 'compute%s' % self.__name__


class IVirtualCompute(Interface):
    """A virtual compute."""


class Computes(AddingContainer):
    __contains__ = Compute

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
                    computes[item.__name__] = Symlink(item.__name__, item)
                if IContainer.providedBy(item):
                    collect(item)

        collect(machines)
        return computes

    def _add(self, item):
        # break an import cycle
        from opennode.oms.zodb import db
        machines = db.get_root()['oms_root'].machines
        return (machines.hangar if IVirtualCompute.providedBy(item) else machines).add(item)


provideSubscriptionAdapter(ByNameContainerExtension, adapts=(Computes, ))
