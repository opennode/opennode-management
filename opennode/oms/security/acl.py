import logging
import transaction

from zope.authentication.interfaces import IAuthentication
from zope.component import getUtility
from zope.securitypolicy.interfaces import IPrincipalRoleManager

from opennode.oms.model.traversal import traverse_path
from opennode.oms.security.interaction import new_interaction
from opennode.oms.security.permissions import Role
from opennode.oms.zodb import db


log = logging.getLogger(__name__)


class NoSuchPermission(Exception):
    pass


def preload_acl_file(stream):
    log.info('Preloading ACL rules...')
    lineno = 0
    try:
        for line in stream:
            path, permspec = line.split(':', 1)
            lineno += 1
            preload_acl_line(path, permspec)
        transaction.commit()
    except NoSuchPermission as e:
        log.error('No such permission: %s line: %s' % (e, line))
        transaction.abort()


@db.ro_transact
def preload_acl_line(path, permspec, meta={}):
    obj = traverse_path(db.get_root()['oms_root'], path[1:])
    auth = getUtility(IAuthentication, context=None)
    interaction = new_interaction(auth.getPrincipal('root'))
    with interaction:
        prinrole = IPrincipalRoleManager(obj)
        action_map = {'allow': prinrole.assignRoleToPrincipal,
                      'deny': prinrole.removeRoleFromPrincipal,
                      'unset': prinrole.unsetRoleForPrincipal}

        permtype, kind, principal, perms = permspec.split('#', 1)[0].strip().split(':', 3)

        if not perms:
            return

        if kind == 'g':
            principal = 'g:' + principal

        for perm in perms.strip().split(','):
            if perm not in Role.nick_to_role:
                raise NoSuchPermission(perm)
            role = Role.nick_to_role[perm].id
            log.info('  %s %s on %s to %s' % (permtype, perm, obj, principal))
            action_map[permtype](role, principal)
