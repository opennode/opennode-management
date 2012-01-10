import hashlib

from base64 import encodestring as encode
from base64 import decodestring as decode
from grokcore.component import subscribe
from zope.authentication.interfaces import IAuthentication, PrincipalLookupError
from zope.component import provideUtility
from zope.interface import implements
from zope.securitypolicy.interfaces import IRole
from zope.securitypolicy.principalrole import principalRoleManager
from zope.securitypolicy.rolepermission import rolePermissionManager
from zope.securitypolicy.role import Role
from twisted.cred.checkers import FilePasswordDB
from twisted.python import log
from opennode.oms.endpoint.ssh.pubkey import InMemoryPublicKeyCheckerDontUse

from opennode.oms.core import IApplicationInitializedEvent
from opennode.oms.config import get_config
from opennode.oms.security.principals import User


class AuthenticationUtility:
    implements(IAuthentication)

    def getPrincipal(self, id):
        if id == None:
            return User('oms.anonymous')
        else:
            return User(id)

        raise PrincipalLookupError(id)


provideUtility(AuthenticationUtility())


# checkers

def ssha_hash(user, password, encoded_password):
    salt = decode(encoded_password[6:])[-4:]

    h = hashlib.sha1(password)
    h.update(salt)
    return "{SSHA}" + encode(h.digest() + salt).rstrip()


def checkers():
    password_checker = FilePasswordDB(get_config().get('auth', 'passwd_file'), hash=ssha_hash)
    pubkey_checker = InMemoryPublicKeyCheckerDontUse()
    return [password_checker, pubkey_checker]


@subscribe(IApplicationInitializedEvent)
def setup_roles(event):
    for i in file(get_config().get('auth', 'roles_file')):
        role, permissions = i.split(':', 3)
        provideUtility(Role(role, role), IRole, role)
        for perm in permissions.split(','):
            if perm.strip():
                rolePermissionManager.grantPermissionToRole(perm.strip(), role.strip())


@subscribe(IApplicationInitializedEvent)
def setup_permissions(event):
    for i in file(get_config().get('auth', 'passwd_file')):
        try:
            user, _, roles = i.split(':', 3)
        except ValueError:
            log.err("Invalid password file format")
        else:
            for role in roles.split(','):
                if role.strip():
                    principalRoleManager.assignRoleToPrincipal(role.strip(), user.strip())
