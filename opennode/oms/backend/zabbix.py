from __future__ import absolute_import

from grokcore.component import subscribe
from opennode.oms.config import get_config
from opennode.oms.model.form import IModelCreatedEvent, IModelDeletedEvent
from opennode.oms.model.model.compute import ICompute
from opennode.oms.model.model.hangar import IHangar

import zabbix_api

class ZabbixOperationException(Exception):
    pass

@subscribe(ICompute, IModelCreatedEvent)
def add_compute_to_zabbix(model, event):
    if IHangar.providedBy(model.__parent__):
        return
    config = get_config()
    if config.get('general', 'zabbix_enabled') != 'yes':
        return
    zapi = _zabbix_login()
    try:
        # check if a compute is already registered in zabbix
        candidates = zapi.host.get({'output': 'shorten',
                                   'filter': {'ip': [model.ipv4_address],
                                               }
                                     
                                    })
        if len(candidates) > 1:
            raise ZabbixOperationException, \
                    "Multiple matching zabbix entries for the compute: %s" %len(candidates) 
        elif len(candidates) == 1:
            model.zabbix_id = int(candidates[0]['hostid'])
        else:
            resp = zapi.host.create({'host': model.hostname,
                  'dns': model.hostname,
                  'ip': model.ipv4_address,
                  'useip': 1,
                  'groups': [{'groupid': config.get('zabbix', 'hostgroup.id')},],
                  'templates': [{'templateid': config.get('zabbix', 'template.id')}]})
            model.zabbix_id = resp['hostids'][0]
    except zabbix_api.Already_Exists:
        pass

@subscribe(ICompute, IModelDeletedEvent)
def remove_compute_from_zabbix(model, event):
    if IHangar.providedBy(model.__parent__):
        return
    if model.zabbix_id is not None: # we don't have registration for that
        zapi = _zabbix_login()
        zapi.host.delete({'hostid': model.zabbix_id})

def _zabbix_login():
    config = get_config()
    zapi = zabbix_api.ZabbixAPI(server=config.get('zabbix', 'server'), path='')
    zapi.login(config.get('zabbix', 'username'), config.get('zabbix', 'password'))
    return zapi

