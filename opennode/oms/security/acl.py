import logging
import os
import transaction

from grokcore.component import subscribe
from twisted.internet import defer
from zope.authentication.interfaces import IAuthentication
from zope.component import getUtility
from zope.securitypolicy.interfaces import IPrincipalRoleManager

from opennode.oms.core import IApplicationInitializedEvent
from opennode.oms.config import get_config
from opennode.oms.model.traversal import traverse1
from opennode.oms.security.interaction import new_interaction
from opennode.oms.security.permissions import Role
from opennode.oms.zodb import db


log = logging.getLogger(__name__)


class NoSuchPermission(Exception):
    pass


@subscribe(IApplicationInitializedEvent)
@defer.inlineCallbacks
def setup_permissions(event):
    if event.test:
        preload_acl_file('')
        return

    acl_file = get_config().getstring('auth', 'acl_file', 'oms_acl')
    if not os.path.exists(acl_file):
        log.warning("ACL file doesn't exist")
        return

    yield preload_acl_file(file(acl_file), filename=acl_file)


@db.ro_transact
def preload_acl_file(iterable, filename=''):
    log.info('Preloading ACL rules...')
    lineno = 0
    try:
        for line in iterable:
            specline = line.split('#', 1)[0]
            if not specline:
                continue
            path, permspec = specline.split(':', 1)
            lineno += 1
            preload_acl_line(path, permspec, filename, lineno)
        transaction.commit()
    except NoSuchPermission as e:
        log.error('No such permission: \'%s\'; file: \'%s\' line: %s' % (e, filename, lineno))
        log.info('Available permissions: %s' % Role.nick_to_role.keys())
        transaction.abort()


def preload_acl_line(path, permspec, filename='-', lineno='-'):
    obj = traverse1(path[1:])

    if obj is None:
        log.warning('No such object: \'%s\'; file: \'%s\' line: %s' % (path, filename, lineno))
        return

    if obj.__transient__:
        log.warning("Transient object %s always inherits permissions from its parent", path)
        return

    auth = getUtility(IAuthentication, context=None)
    interaction = new_interaction(auth.getPrincipal('root'))
    with interaction:
        prinrole = IPrincipalRoleManager(obj)
        action_map = {'allow': prinrole.assignRoleToPrincipal,
                      'deny': prinrole.removeRoleFromPrincipal,
                      'unset': prinrole.unsetRoleForPrincipal}

        permtype, kind, principal, perms = permspec.strip().split(':', 3)

        if not perms:
            log.warning('No permissions specified for object: \'%s\'; file: \'%s\' line: %s'
                        % (path, filename, lineno))
            return

        for perm in perms.strip().split(','):
            if perm not in Role.nick_to_role:
                raise NoSuchPermission(perm)
            role = Role.nick_to_role[perm].id
            log.info('%s \'%s\' on %s (%s) to \'%s\'' % (permtype, perm, path, obj, principal))
            action_map[permtype](role, principal)
