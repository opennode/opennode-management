from __future__ import absolute_import

from zope import schema
from zope.interface import Interface, implements

from .base import Model, Container


class ICompute(Interface):
    architecture = schema.Choice(title=u"Architecture", values=(u'linux', u'win32', u'darwin', u'bsd', u'solaris'))
    hostname = schema.TextLine(title=u"Host name", min_length=3)
    ip_address = schema.TextLine(title=u"IP address", min_length=7, required=False)
    speed = schema.Int(title=u"CPU Speed", description=u"CPU Speed in MHz")
    memory = schema.Int(title=u"RAM Size", description=u"RAM size in MB")
    state = schema.Choice(title=u"State", values=(u'active', u'inactive', u'standby'))


class Compute(Model):
    implements(ICompute)

    ip_address = u'0.0.0.0'
    type = 'unknown'  # XXX: how should this be determined?
                      # and how do we differentiate for ONC physical and virtual computes?
    cpu = "Intel Xeon 12.2GHz"
    memory = 2048,
    os_release = "build 35"
    kernel = "2.6.18-238.9.1.el5.028stab089.1"
    network = 1000
    diskspace = 750
    swap_size = 7777
    diskspace_rootpartition = 77.7
    diskspace_storagepartition = 77.7
    diskspace_vzpartition = 77.7
    diskspace_backuppartition = 77.7
    startup_timestamp = "2011-07-06 01:23:45"

    def __init__(self, architecture, hostname, speed, memory, state, template=None, ip_address=None):
        self.architecture = architecture
        self.hostname = hostname
        self.speed = speed
        self.memory = memory
        self.state = state
        self.template = template
        if ip_address:
            self.ip_address = ip_address

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


class Computes(Container):
    __contains__ = Compute

    def __str__(self):
        return 'Compute list'
