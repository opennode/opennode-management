import hashlib
import os
import pkg_resources
import sys

from base64 import encodestring as encode
from base64 import decodestring as decode
from contextlib import closing
from grokcore.component import GlobalUtility, subscribe
from zope.authentication.interfaces import IAuthentication, PrincipalLookupError
from zope.component import provideUtility, queryUtility
from zope.interface import implements
from zope.security.management import system_user
from zope.securitypolicy.interfaces import IRole
from zope.securitypolicy.principalrole import principalRoleManager
from zope.securitypolicy.rolepermission import rolePermissionManager
from twisted.cred.checkers import FilePasswordDB
from twisted.internet import inotify
from twisted.python import log, filepath

from opennode.oms.endpoint.ssh.pubkey import InMemoryPublicKeyCheckerDontUse

from opennode.oms.core import IApplicationInitializedEvent
from opennode.oms.config import get_config
from opennode.oms.security.permissions import Role
from opennode.oms.security.principals import User, Group


_checkers = None
conf_reload_notifier = inotify.INotify()
conf_reload_notifier.startReading()


class AuthenticationUtility(GlobalUtility):
    implements(IAuthentication)

    def __init__(self):
        self.principals = {}

    def registerPrincipal(self, principal):
        self.principals[principal.id] = principal

    def getPrincipal(self, id):
        if id == None:
            return self.principals['oms.anonymous']
        if id == system_user.id:
            return system_user
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


def setup_conf_reload_watch(path, handler):
    """Registers a inotify watch which will invoke `handler` for passing the open file"""
    conf_reload_notifier.watch(filepath.FilePath(path), callbacks=[lambda self, filepath, mask: handler(filepath.open())])


@subscribe(IApplicationInitializedEvent)
def setup_roles(event):
    perm_file = get_config().get('auth', 'permissions_file')

    if os.path.exists(perm_file):
        setup_conf_reload_watch(perm_file, reload_roles)
        perm_file_factory = file
    else:  # read the content from the egg
        perm_file = os.path.join('../../../', 'oms_permissions')
        perm_file_factory = lambda f: pkg_resources.resource_stream(__name__, f)

    reload_roles(perm_file_factory(perm_file))


def reload_roles(stream):
    print "(Re)Loading OMS permission definitions"
    for i in stream:
        nick, role, permissions = i.split(':', 4)
        oms_role = Role(role, nick)
        provideUtility(oms_role, IRole, role)
        for perm in permissions.split(','):
            if perm.strip():
                rolePermissionManager.grantPermissionToRole(perm.strip(), role.strip())


@subscribe(IApplicationInitializedEvent)
def setup_groups(event):
    groups_file = get_config().get('auth', 'groups_file')
    if not os.path.exists(groups_file):
        print "Groups file doesn't exist, generating a default groups file, use `bin/groups` to customize it"
        with closing(open(groups_file, 'w')) as f:
            f.write(pkg_resources.resource_stream(__name__, os.path.join('../../../', 'oms_groups')).read())

    reload_groups(file(groups_file))
    setup_conf_reload_watch(groups_file, reload_groups)


def reload_groups(stream):
    print "(Re)Loading OMS groups definitions"

    auth = queryUtility(IAuthentication)

    for i in stream:
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

    passwd_file = get_config().get('auth', 'passwd_file')
    if not os.path.exists(passwd_file):
        print "User account and password file doesn't exist"
        print "please set up at least one admin account with `bin/passwd`, e.g:"
        print
        print "  <OMS_ROOT>/bin/passwd -a john -g admins"
        sys.exit(1)

    reload_users(file(passwd_file))
    setup_conf_reload_watch(passwd_file, reload_users)


def reload_users(stream):
    print "(Re)Loading OMS users definitions"

    auth = queryUtility(IAuthentication)
    auth.registerPrincipal(User('oms.anonymous'))

    for i in stream:
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
