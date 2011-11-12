import StringIO
import json
from collections import OrderedDict

import zope.schema
from grokcore.component import context
from zope.component import queryAdapter

from opennode.oms.endpoint.httprest.base import HttpRestView, IHttpRestView
from opennode.oms.model.form import ApplyRawData
from opennode.oms.model.location import ILocation
from opennode.oms.model.model import Machines, Compute
from opennode.oms.model.model.base import IContainer
from opennode.oms.model.model.byname import ByNameContainer
from opennode.oms.model.model.filtrable import IFiltrable
from opennode.oms.model.model.hangar import Hangar
from opennode.oms.model.model.virtualizationcontainer import VirtualizationContainer
from opennode.oms.model.model.symlink import follow_symlinks
from opennode.oms.model.model.actions import ActionsContainer
from opennode.oms.util import get_direct_interfaces


class DefaultView(HttpRestView):
    context(object)

    def render(self, request):
        obj = self.context
        # NODE: code copied from commands.py:CatCmd
        schemas = get_direct_interfaces(obj)
        if len(schemas) == 0:
            raise Exception("Unable to create a printable representation.\n")
            return

        data = OrderedDict()
        for schema in schemas:
            fields = zope.schema.getFieldsInOrder(schema)
            for key, field in fields:
                key = key.encode('utf8')
                data[key] = field.get(obj)

        data['id'] = obj.__name__

        return data

    def render_PUT(self, request):
        data = json.load(request.content)

        form = ApplyRawData(data, self.context)
        if not form.errors:
            form.apply()
        else:
            sio = StringIO.StringIO()
            form.write_errors(to=sio)
            raise Exception(sio.getvalue())

        return json.dumps('ok')


class ContainerView(DefaultView):
    context(IContainer)

    def render(self, request):
        depth = int(request.args.get('depth', ['1'])[0])
        return self.render_recursive(request, depth, top_level=True)

    def render_recursive(self, request, depth, top_level=False):
        container_properties = {'id': self.context.__name__}

        try:
            container_properties = super(ContainerView, self).render(request)
        except Exception:
            pass

        if depth < 1:
            return container_properties

        items = map(follow_symlinks, self.context.listcontent())

        q = request.args.get('q', [''])[0]
        q = q.decode('utf-8')

        if q:
            items = [item for item in items if IFiltrable(item).match(q)]

        children = [IHttpRestView(item).render_recursive(request, depth - 1) for item in items if queryAdapter(item, IHttpRestView) and not self.blacklisted(item)]

        # backward compatibility:
        # top level results for pure containers are plain lists
        if top_level and (not container_properties or len(container_properties.keys()) == 1):
            return children

        #if not top_level or depth > 1:
        #if depth > 1:
        if not top_level or depth > 1:
            container_properties['children'] = children
        return  container_properties

    def blacklisted(self, item):
        return isinstance(item, ByNameContainer)


class MachinesView(ContainerView):
    context(Machines)

    def blacklisted(self, item):
        return super(MachinesView, self).blacklisted(item) or isinstance(item, Hangar)


class VirtualizationContainerView(ContainerView):
    context(VirtualizationContainer)

    def blacklisted(self, item):
        return super(VirtualizationContainerView, self).blacklisted(item) or isinstance(item, ActionsContainer)


class ComputeView(HttpRestView):
    context(Compute)

    def render(self, request):

        return {'id': self.context.__name__,
                'hostname': self.context.hostname,
                'ipv4_address': self.context.ipv4_address,
                'ipv6_address': self.context.ipv6_address,
                'url': ILocation(self.context).get_url(),
                'type': self.context.type,
                'features': [i.__name__ for i in self.context.implemented_interfaces()],
                'state': self.context.state,

                'cpu': self.context.cpu,
                'memory': self.context.memory,
                'os_release': self.context.os_release,
                'kernel': self.context.kernel,
                'network_usage': self.context.network_usage,
                'diskspace': self.context.diskspace,
                'swap_size': self.context.swap_size,
                'diskspace_rootpartition': self.context.diskspace_rootpartition,
                'diskspace_storagepartition': self.context.diskspace_storagepartition,
                'diskspace_vzpartition': self.context.diskspace_vzpartition,
                'diskspace_backuppartition': self.context.diskspace_backuppartition,
                'startup_timestamp': self.context.startup_timestamp,
                'bridge_interfaces': self._network_interfaces(request),
                'children': self._children(request),
                }

    def _children(self, request):
        ret = [
            self._vms(request),
        ]
        return [i for i in ret if i]

    def _vms(self, request):
        if not self.context['vms']:
            return None
        return IHttpRestView(self.context['vms']).render_recursive(request, 2)

    def _network_interfaces(self, request):
        try:
            return IHttpRestView(self.context['interfaces']).render_recursive(request, 1)['children']
        except:
            #return self._dummy_network_data()['bridge_interfaces']
            return []

    def _dummy_network_data(self):
        return {
            'bridge_interfaces': [{
                'id': 'vmbr1',
                'ipv4_address': '192.168.1.40/24',
                'ipv6_address': 'fe80::64ac:39ff:fe4a:e596/64',
                'bcast': '192.168.1.255',
                'hw_address': '00:00:00:00:00:00',
                'metric': 1,
                'stp': False,
                'rx': '102.5MiB',
                'tx': '64.0MiB',
                'members': ['eth0', 'vnet0', 'vnet1', 'vnet5', 'vnet6',],
            }, {
                'id': 'vmbr2',
                'ipv4_address': '192.168.2.40/24',
                'ipv6_address': 'fe80::539b:28dd:db3b:c407/64',
                'bcast': '192.168.2.255',
                'hw_address': '00:00:00:00:00:00',
                'metric': 1,
                'stp': False,
                'rx': '92.1MiB',
                'tx': '89.9MiB',
                'members': ['eth1', 'vnet1', 'vnet2', 'vnet3', 'vnet4',],
            }, {
                'id': 'vmbr3',
                'ipv4_address': '192.168.2.40/24',
                'ipv6_address': 'fe80::539b:28dd:db3b:c407/64',
                'bcast': '192.168.2.255',
                'hw_address': '00:00:00:00:00:00',
                'metric': 1,
                'stp': False,
                'rx': '92.1MiB',
                'tx': '89.9MiB',
                'members': ['eth2', 'vnet10', 'vnet11', 'vnet12', 'vnet13',],
            }, {
                'id': 'vmbr4',
                'ipv4_address': '192.168.2.40/24',
                'ipv6_address': 'fe80::539b:28dd:db3b:c407/64',
                'bcast': '192.168.2.255',
                'hw_address': '00:00:00:00:00:00',
                'metric': 1,
                'stp': False,
                'rx': '92.1MiB',
                'tx': '89.9MiB',
                'members': ['eth3', 'vnet14', 'vnet15', 'vnet16', 'vnet17',],
            }, {
                'id': 'vmbr5',
                'ipv4_address': '192.168.2.40/24',
                'ipv6_address': 'fe80::539b:28dd:db3b:c407/64',
                'bcast': '192.168.2.255',
                'hw_address': '00:00:00:00:00:00',
                'metric': 1,
                'stp': False,
                'rx': '92.1MiB',
                'tx': '89.9MiB',
                'members': ['eth4', 'vnet18', 'vnet19', 'vnet20', 'vnet21',],
            }, {
                'id': 'nobr',
                'members': ['vnet7', 'vnet8'],
            }],
            'ip-routes': [{
                'dest': '192.168.1.125',
                'gateway': '0.0.0.0',
                'genmask': '255.255.255.255',
                'flags': 'UH',
                'metric': 0,
                'interface': 'venet0',
            }, {
                'dest': '192.168.2.125',
                'gateway': '0.0.0.0',
                'genmask': '255.255.255.255',
                'flags': 'UH',
                'metric': 0,
                'interface': 'venet1',
            }, {
                'dest': '192.168.3.125',
                'gateway': '0.0.0.0',
                'genmask': '255.255.255.255',
                'flags': 'UH',
                'metric': 0,
                'interface': 'venet2',
            }],
        }
