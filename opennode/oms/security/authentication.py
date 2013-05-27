import grp
import hashlib
import logging
import os
import pkg_resources
import pam
import pwd
import sys
import time

from base64 import decodestring as decode
from base64 import encodestring as encode
from contextlib import closing
from grokcore.component import GlobalUtility, subscribe
from twisted.cred.checkers import FilePasswordDB
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import IUsernamePassword
from twisted.cred.error import UnauthorizedLogin
from twisted.internet import inotify, defer
from twisted.python import filepath
from zope.authentication.interfaces import IAuthentication
from zope.component import getUtility, provideUtility, queryUtility
from zope.interface import implements
from zope.security._definitions import thread_local
from zope.security.checker import getChecker
from zope.security.management import system_user
from zope.securitypolicy.interfaces import IRole
from zope.securitypolicy.principalpermission import principalPermissionManager
from zope.securitypolicy.principalrole import principalRoleManager
from zope.securitypolicy.rolepermission import rolePermissionManager

from opennode.oms.core import IApplicationInitializedEvent
from opennode.oms.config import get_config
from opennode.oms.endpoint.ssh.pubkey import InMemoryPublicKeyCheckerDontUse
from opennode.oms.security import acl, checker
from opennode.oms.security.interaction import new_interaction
from opennode.oms.security.permissions import Role
from opennode.oms.security.principals import User, Group


log = logging.getLogger(__name__)

_checkers = None
conf_reload_notifier = inotify.INotify()
conf_reload_notifier.startReading()


def get_linux_groups_for_user(user):
    groups = [g.gr_name for g in grp.getgrall() if user in g.gr_mem]
    gid = pwd.getpwnam(user).pw_gid
    groups.append(grp.getgrgid(gid).gr_name)
    return groups


class PamAuthChecker(object):
    """ Check user credentials using PAM infrastructure """
    credentialInterfaces = IUsernamePassword
    implements(ICredentialsChecker)

    def requestAvatarId(self, credentials):
        if pam.authenticate(credentials.username, credentials.password):
            log.info('Successful login with PAM for %s' % credentials.username)
            auth = getUtility(IAuthentication)
            oms_user = User(credentials.username)
            oms_user.groups.extend(get_linux_groups_for_user(credentials.username))
            log.info(' Adding user groups: %s' % ', '.join(oms_user.groups))
            for g in get_linux_groups_for_user(credentials.username):
                auth.registerPrincipal(Group(g))
            auth.registerPrincipal(oms_user)
            return defer.succeed(credentials.username)
        log.warning(' Authentication failed with PAM for %s' % credentials.username)
        return defer.fail(UnauthorizedLogin('Invalid credentials'))


class AuthenticationUtility(GlobalUtility):
    implements(IAuthentication)

    def __init__(self):
        self.principals = {}

    def registerPrincipal(self, principal):
        if type(principal) is Group:
            self.principals['g:' + principal.id] = principal
        else:
            self.principals[principal.id] = principal

    def getPrincipal(self, id):
        if id is None:
            return self.principals['oms.anonymous']
        if id == system_user.id:
            return system_user
        else:
            p = self.principals.get(id)
            if p is None:
                p = self.principals.get('g:' + id)
            return p
        log.debug('getPrincipal %s not in (None, %s, %s). Defaulting to anonymous'
                  % (id, system_user.id, ', '.join(self.principals.keys())))
        # default to anonymous if nothing more specific is found
        return self.principals['oms.anonymous']


# checkers
def ssha_hash(user, password, encoded_password):
    salt = decode(encoded_password[6:])[-4:]

    h = hashlib.sha1(password)
    h.update(salt)
    return "{SSHA}" + encode(h.digest() + salt).rstrip()


def checkers():
    global _checkers
    if _checkers is None:
        pam_checker = PamAuthChecker() if get_config().getboolean('auth', 'use_pam') else None
        password_checker = FilePasswordDB(get_config().get('auth', 'passwd_file'), hash=ssha_hash)
        pubkey_checker = InMemoryPublicKeyCheckerDontUse()
        _checkers = filter(None, [pam_checker, password_checker, pubkey_checker])
    return _checkers


def setup_conf_reload_watch(path, handler):
    """Registers a inotify watch which will invoke `handler` for passing the open file"""

    def delayed_handler(self, filepath, mask):
        time.sleep(1)
        handler(filepath.open())

    conf_reload_notifier.watch(filepath.FilePath(path),
                               callbacks=[delayed_handler])


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
    log.info("(Re)Loading OMS permission definitions")
    for line in stream:
        nick, role, permissions = line.split(':', 4)
        oms_role = Role(role, nick)
        provideUtility(oms_role, IRole, role)
        for perm in permissions.split(','):
            if perm.strip():
                rolePermissionManager.grantPermissionToRole(perm.strip(), role.strip())


@subscribe(IApplicationInitializedEvent)
def setup_groups(event):
    if event.test:
        return

    groups_file = get_config().get('auth', 'groups_file')
    if not os.path.exists(groups_file):
        log.msg("Groups file doesn't exist, generating a default groups file, "
                "use `bin/groups` to customize it", system='auth')
        with closing(open(groups_file, 'w')) as f:
            f.write(pkg_resources.resource_stream(__name__, os.path.join('../../../', 'oms_groups')).read())

    reload_groups(file(groups_file))
    setup_conf_reload_watch(groups_file, reload_groups)


def reload_groups(stream):
    log.info("(Re)Loading OMS groups definitions")

    auth = queryUtility(IAuthentication)

    for line in stream:
        try:
            group, roles = line.split(':', 2)
        except ValueError:
            log.info("Invalid groups file format")
        else:
            oms_group = Group(group.strip())
            auth.registerPrincipal(oms_group)

            for role in roles.split(','):
                if role.strip():
                    principalRoleManager.assignRoleToPrincipal(role.strip(), group.strip())


@subscribe(IApplicationInitializedEvent)
def setup_permissions(event):
    if event.test:
        reload_users('')
        return

    passwd_file = get_config().get('auth', 'passwd_file')
    if not os.path.exists(passwd_file):
        print "User account and password file doesn't exist"
        print "please set up at least one admin account with `bin/passwd`, e.g:"
        print
        print "  <OMS_ROOT>/bin/passwd -a john -g admins"
        sys.exit(1)

    reload_users(file(passwd_file))
    setup_conf_reload_watch(passwd_file, reload_users)


@subscribe(IApplicationInitializedEvent)
@defer.inlineCallbacks
def setup_acl(event):
    if event.test:
        acl.preload_acl_file('')
        return

    acl_file = get_config().getstring('auth', 'acl_file', 'oms_acl')
    if not os.path.exists(acl_file):
        log.warning("ACL file doesn't exist")
        return

    yield acl.preload_acl_file(file(acl_file), filename=acl_file)


def create_special_principals():
    auth = queryUtility(IAuthentication)

    auth.registerPrincipal(User('oms.anonymous'))

    groot = Group('root')
    auth.registerPrincipal(groot)

    root = User('root')
    root.groups.append('root')
    auth.registerPrincipal(root)

    # TODO: create/use a global registry of permissions
    permissions = ['read', 'modify', 'create', 'add', 'remove', 'delete', 'view', 'traverse',
                   'zope.Security']

    root_role = Role('root', 'root')
    provideUtility(root_role, IRole, 'root')
    for perm in permissions:
        rolePermissionManager.grantPermissionToRole(perm, 'root')

    principalRoleManager.assignRoleToPrincipal('root', 'root')

    owner_role = Role('owner', 'o')
    provideUtility(owner_role, IRole, 'owner')
    for perm in permissions:
        rolePermissionManager.grantPermissionToRole(perm, 'owner')

    for permission in permissions:
        rolePermissionManager.grantPermissionToRole(permission, 'root')
        rolePermissionManager.grantPermissionToRole(permission, 'owner')

    auth.registerPrincipal(User('oms.rest_options'))

    principalPermissionManager.grantPermissionToPrincipal('rest', 'oms.rest_options')


def reload_users(stream):
    log.info("(Re)Loading OMS users definitions")

    create_special_principals()
    auth = queryUtility(IAuthentication)

    lineno = 0
    for line in stream:
        lineno += 1
        try:
            user, _, groups = line.split(':', 2)
        except ValueError:
            log.error("Invalid password file format: '%s':%s" % (stream.name, lineno))
        else:
            if ':' in groups:
                groups, uid = groups.split(':', 1)
                uid = int(uid) if uid.strip() != 'None' else None
            else:
                uid = None
            oms_user = User(user.strip(), uid=uid)
            oms_user.groups = [group.strip() for group in groups.split(',') if group.strip()]
            log.debug('Loaded %s', oms_user)
            auth.registerPrincipal(oms_user)


class Sudo(object):

    def __init__(self, obj):
        self._obj = obj
        try:
            self.checker = getChecker(self._obj)
        except TypeError:
            self.checker = None
        else:
            if not isinstance(self.checker, checker.Checker):
                log.debug('self.checker is %s', self.checker)
                self.checker = thread_local

    def __enter__(self):
        if self.checker is None:
            return

        self.checker.previous_interaction = self.checker.interaction
        self.checker.interaction = new_interaction('root')

    def __exit__(self, *args):
        if self.checker is None:
            return

        self.checker.interaction = self.checker.previous_interaction
        del self.checker.previous_interaction
