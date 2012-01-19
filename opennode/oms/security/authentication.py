import hashlib
import os
import sys

from base64 import encodestring as encode
from base64 import decodestring as decode
from grokcore.component import GlobalUtility, subscribe
from zope.authentication.interfaces import IAuthentication, PrincipalLookupError
from zope.component import provideUtility, queryUtility
from zope.interface import implements
from zope.securitypolicy.interfaces import IRole
from zope.securitypolicy.principalrole import principalRoleManager
from zope.securitypolicy.rolepermission import rolePermissionManager
from twisted.cred.checkers import FilePasswordDB
from twisted.python import log
from opennode.oms.endpoint.ssh.pubkey import InMemoryPublicKeyCheckerDontUse

from opennode.oms.core import IApplicationInitializedEvent
from opennode.oms.config import get_config
from opennode.oms.security.permissions import Role
from opennode.oms.security.principals import User, Group


_checkers = None


class AuthenticationUtility(GlobalUtility):
    implements(IAuthentication)

    def __init__(self):
        self.principals = {}

    def registerPrincipal(self, principal):
        self.principals[principal.id] = principal

    def getPrincipal(self, id):
        if id == None:
            return self.principals['oms.anonymous']
        elif id in self.principals:
            return self.principals[id]

        raise PrincipalLookupError(id)


# checkers

def ssha_hash(user, password, encoded_password):
    salt = decode(encoded_password[6:])[-4:]

    h = hashlib.sha1(password)
    h.update(salt)
    return "{SSHA}" + encode(h.digest() + salt).rstrip()


def checkers():
    global _checkers
    if _checkers == None:
        password_checker = FilePasswordDB(get_config().get('auth', 'passwd_file'), hash=ssha_hash)
        pubkey_checker = InMemoryPublicKeyCheckerDontUse()
        _checkers = [password_checker, pubkey_checker]
    return _checkers


@subscribe(IApplicationInitializedEvent)
def setup_roles(event):
    for i in file(get_config().get('auth', 'permissions_file')):
        nick, role, permissions = i.split(':', 4)
        oms_role = Role(role, nick)
        provideUtility(oms_role, IRole, role)
        for perm in permissions.split(','):
            if perm.strip():
                rolePermissionManager.grantPermissionToRole(perm.strip(), role.strip())


@subscribe(IApplicationInitializedEvent)
def setup_groups(event):
    auth = queryUtility(IAuthentication)

    groups_file = get_config().get('auth', 'groups_file')
    if not os.path.exists(groups_file):
        log.err("Groups file doesn't exist, please set up groups with `bin/groups`")
        sys.exit(1)

    for i in file(groups_file):
        try:
            group, roles = i.split(':', 2)
        except ValueError:
            log.err("Invalid groups file format")
        else:
            oms_group = Group(group.strip())
            auth.registerPrincipal(oms_group)

            for role in roles.split(','):
                if role.strip():
                    principalRoleManager.assignRoleToPrincipal(role.strip(), group.strip())


@subscribe(IApplicationInitializedEvent)
def setup_permissions(event):
    auth = queryUtility(IAuthentication)
    auth.registerPrincipal(User('oms.anonymous'))

    passwd_file = get_config().get('auth', 'passwd_file')
    if not os.path.exists(passwd_file):
        log.err("User account and password file doesn't exist, please set up accounts with `bin/passwd`")
        sys.exit(1)

    for i in file(passwd_file):
        try:
            user, _, groups = i.split(':', 3)
        except ValueError:
            log.err("Invalid password file format")
        else:
            oms_user = User(user.strip())
            for group in groups.split(','):
                if group.strip():
                    oms_user.groups.append(group.strip())

            auth.registerPrincipal(oms_user)
