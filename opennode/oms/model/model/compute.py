from __future__ import absolute_import

from grokcore.component import context, Subscription, baseclass
from zope import schema
from zope.component import provideSubscriptionAdapter
from zope.interface import Interface, implements, alsoProvides

from .actions import ActionsContainerExtension
from .base import IContainer, Container, AddingContainer, IIncomplete, IDisplayName, IContainerExtender
from .byname import ByNameContainerExtension
from .console import Consoles
from .network import NetworkInterfaces
from .search import ModelTags
from .symlink import Symlink
from opennode.oms.backend.operation import IFuncInstalled
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
    ncpus = schema.Int(title=u"CPU/cores number", description=u"Number of CPU/cores", required=False)
    cpu_limit = schema.Float(title=u"CPU limit", description=u"Cpu limit", required=False)
    diskspace = schema.Int(title=u"Disk size", description=u"Size of main volume", required=False)


class IInCompute(Interface):
    """Implementors of this interface can be contained in a `Compute` container."""


class IDeployed(Interface):
    """Marker interface implemented when the compute has been deployed."""


class Compute(Container):
    """A compute node."""

    implements(ICompute, IDisplayName)

    __contains__ = IInCompute

    _ipv4_address = u'0.0.0.0/32'
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
    ncpus = 1
    cpu_limit = 1.0
    autostart = False

    def __init__(self, architecture, hostname, memory, state, template=None, ipv4_address=None):
        super(Compute, self).__init__()

        self.architecture = architecture
        self.hostname = hostname
        self.memory = memory
        self.state = state
        self.template = template
        if ipv4_address:
            self._ipv4_address = ipv4_address

        if self.template:
            alsoProvides(self, IVirtualCompute)
        else:
            alsoProvides(self, IFuncInstalled)

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

    def get_consoles(self):
        if not self._items.has_key('consoles'):
            self._add(Consoles())
        return self._items['consoles']

    def set_consoles(self, value):
        if self._items.has_key('consoles'):
            del self._items['consoles']
        self._add(value)

    consoles = property(get_consoles, set_consoles)


    def get_interfaces(self):
        if not self._items.has_key('interfaces'):
            self._add(NetworkInterfaces())
        return self._items['interfaces']

    def set_interfaces(self, value):
        if self._items.has_key('interfaces'):
            del self._items['interfaces']
        self._add(value)

    interfaces = property(get_interfaces, set_interfaces)

    @property
    def ipv4_address(self):
        if not self._items.has_key('interfaces'):
            return self._ipv4_address
        addresses = [i.ipv4_address for i in self._items['interfaces'] if i.ipv4_address]
        if not addresses:
            return self._ipv4_address
        return addresses[0]


class ComputeTags(ModelTags):
    context(Compute)

    def auto_tags(self):
        res =  [u'arch:'+self.context.architecture, u'state:'+self.context.state]

        from .virtualizationcontainer import IVirtualizationContainer
        if IVirtualCompute.providedBy(self.context) and IVirtualizationContainer.providedBy(self.context.__parent__):
            res.append(u'virt_type:'+self.context.__parent__.backend)

        return res


class IVirtualCompute(Interface):
    """A virtual compute."""

    autostart = schema.Bool(title=u"Autostart", description=u"Start on boot", required=False)


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

    def __delitem__(self, key):
        item = self._items[key]
        if isinstance(item, Symlink):
            del item.target.__parent__[item.target.__name__]


provideSubscriptionAdapter(ActionsContainerExtension, adapts=(Compute, ))
provideSubscriptionAdapter(ByNameContainerExtension, adapts=(Computes, ))

# #####################
# hack (but lowercase)
#
# let the onc guy work
# #####################


class TemplatesComputeExtension(Subscription):
    implements(IContainerExtender)
    baseclass()

    def extend(self):
        from opennode.oms.zodb import db
        if self.context._items.has_key('vms'):
            return {'templates': Symlink('templates', db.get_root()['oms_root']['templates'])}
        return {}


provideSubscriptionAdapter(TemplatesComputeExtension, adapts=(Compute, ))
