from __future__ import absolute_import

from grokcore.component import context, Subscription, baseclass
from zope import schema
from zope.component import provideSubscriptionAdapter, provideAdapter
from zope.interface import Interface, implements, alsoProvides

from .actions import ActionsContainerExtension
from .base import IContainer, Container, AddingContainer, IIncomplete, IDisplayName, IContainerExtender
from .byname import ByNameContainerExtension
from .console import Consoles
from .network import NetworkInterfaces
from .search import ModelTags
from .stream import MetricsContainerExtension, IMetrics
from .symlink import Symlink
from opennode.oms.backend.operation import IFuncInstalled
from opennode.oms.model.schema import Path
from opennode.oms.util import adapter_value


class ICompute(Interface):
    # Network parameters
    hostname = schema.TextLine(
        title=u"Host name", min_length=3)
    ipv4_address = schema.TextLine(
        title=u"IPv4 address", min_length=7, required=False)
    ipv6_address = schema.TextLine(
        title=u"IPv6 address", min_length=6, required=False)

    # Hardware/platform info
    architecture = schema.Tuple(
        title=u"Architecture", description=u"OS arch, OS type, OS distribution/flavour",
        value_type=schema.TextLine(), max_length=3, min_length=3,
        required=False)
    cpu_info = schema.TextLine(
        title=u"CPU Info", description=u"Info about the CPU such as model, speed in Hz, cache size",
        required=False)
    os_release = schema.TextLine(
        title=u"OS Release", description=u"OS version info",
        required=False)
    kernel = schema.TextLine(
        title=u"Kernel", description=u"Kernel version (if applicable)",
        required=False)
    disk_info = schema.TextLine(
        title=u"Disk Info", description=u"Info about the physical installed disk(s)",
        required=False)
    memory_info = schema.TextLine(
        title=u"Memory Info", description=(u"Info about the physical installed memory "
                     "banks such as model, make, speed, latency"),
        required=False)

    # State
    state = schema.Choice(
        title=u"State", values=(u'active', u'inactive', u'suspended'))
    effective_state = schema.TextLine(
        title=u"Effective state", readonly=True, required=False)

    # Processing/network capabilities:
    num_cores = schema.Int(
        title=u"Num. Cores", description=u"Total number of cores across all CPUs",
        required=False)
    memory = schema.Int(
        title=u"RAM Size", description=u"RAM size in MB",
        required=False)
    diskspace = schema.Dict(
        title=u"Disk size", description=u"List of disk partition sizes",
        key_type=schema.TextLine(), value_type=schema.Float(),
        required=False)
    network = schema.Float(
        title=u"Network", description=u"Network bandwidth in Mbps",
        required=False)
    swap_size = schema.Int(
        title=u"Swap Size", description=u"Swap size",
        required=False)

    # Resource utilization/load:
    cpu_usage = schema.Tuple(
        title=u"CPU Load", description=u"CPU load during the past 1, 5 and 15 minutes",
        value_type=schema.Float(),
        required=False)
    memory_usage = schema.Float(
        title=u"Memory Usage", description=u"Memory usage in MB",
        required=False)
    diskspace_usage = schema.Dict(
        title=u"Diskspace Utilization", description=u"List of disk partition usages",
        key_type=schema.TextLine(), value_type=schema.Float(),
        required=False)
    network_usage = schema.Tuple(
        title=u"Network Load", description=u"Network load in Mb/s (incoming and outgoing)",
        value_type=schema.Float(),
        required=False)

    # VM only
    template = Path(title=u"Template", required=False, base_path='/templates/by-name/')
    cpu_limit = schema.Float(title=u"CPU Limit", description=u"CPU usage limit", required=False)


class IInCompute(Interface):
    """Implementors of this interface can be contained in a `Compute` container."""


class IDeployed(Interface):
    """Marker interface implemented when the compute has been deployed."""

class IUndeployed(Interface):
    """Marker interface implemented when the compute has not been deployed yet."""


class Compute(Container):
    """A compute node."""

    implements(ICompute, IDisplayName)

    __contains__ = IInCompute

    _ipv4_address = u'0.0.0.0/32'
    ipv6_address = u'::/128'
    type = 'unknown'  # XXX: how should this be determined?
                      # and how do we differentiate for ONC physical and virtual computes?
    architecture = (u'x86_64', u'linux', u'centos')
    cpu_info = u"Intel Xeon 12.2GHz"
    disk_info = u"Seagate Barracuda SuperSaver 2000TB BuyNow!"
    memory_info = u"1333MHz DDR SuperGoodMemory!"

    os_release = u"build 35"
    kernel = u"2.6.18-238.9.1.el5.028stab089.1"

    num_cores = 1
    memory = 2048,
    network = 100.0
    diskspace = {
        u'total': 2000.0,
        u'root': 500.0,
        u'boot': 100.0,
        u'storage': 1000.0,
    }
    swap_size = 4192


    cpu_usage = (0.1, 0.11, 0.14)
    memory_usage = 773.2
    network_usage = (55.2, 21.9)
    diskspace_usage = {
        u'root': 249.0,
        u'boot': 49.3,
        u'storage': 748.3,
    }

    cpu_limit = 1.0

    autostart = False
    startup_timestamp = "2011-07-06 01:23:45"

    def __init__(self, hostname, state, memory=None, template=None, ipv4_address=None):
        super(Compute, self).__init__()

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
        alsoProvides(self, IUndeployed)

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
        return unicode(addresses[0])


class ComputeTags(ModelTags):
    context(Compute)

    def auto_tags(self):
        res =  [u'state:'+self.context.state]
        if self.context.architecture:
            for i in self.context.architecture:
                res.append(u'arch:'+i)

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


provideAdapter(adapter_value(['cpu_usage', 'memory_usage', 'network_usage', 'diskspace_usage']), adapts=(Compute,), provides=(IMetrics))


provideSubscriptionAdapter(ActionsContainerExtension, adapts=(Compute, ))
provideSubscriptionAdapter(ByNameContainerExtension, adapts=(Computes, ))
provideSubscriptionAdapter(MetricsContainerExtension, adapts=(Compute, ))


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
