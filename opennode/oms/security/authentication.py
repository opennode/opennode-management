import grp
import hashlib
import logging
import os
import pkg_resources
import pam
import pwd
import sys
import time
import subprocess
from sys import platform as _platform
import json

from base64 import decodestring as decode
from base64 import encodestring as encode
from contextlib import closing
from grokcore.component import GlobalUtility, subscribe
from twisted.cred.checkers import FilePasswordDB
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import IUsernamePassword
from twisted.cred.error import UnauthorizedLogin
from twisted.internet import defer
from twisted.python import filepath
from zope.authentication.interfaces import IAuthentication
from zope.component import getUtility, provideUtility, queryUtility
from zope.interface import implements
from zope.security.proxy import Proxy, getObject, getChecker
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

if _platform == "linux" or _platform == "linux2":
    from twisted.internet import inotify
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


class KeystoneChecker(object):
    """ Validate Keystone token """
    credentialInterfaces = IUsernamePassword
    implements(ICredentialsChecker)

    def validate_and_parse_keystone_token(self, cms_token):
        """Validate Keystone CMS token.
        
        Partially taken from Keystone's common/cms.py module."""
        signing_cert_file_name = get_config().get('keystone', 'signing_cert_file_name')
        ca_file_name = get_config().get('keystone', 'ca_file_name')
        openssl_cmd = get_config().get('keystone', 'openssl_cmd')
        process = subprocess.Popen([openssl_cmd, "cms", "-verify",
                                  "-certfile",
                                  signing_cert_file_name,
                                  "-CAfile", ca_file_name,
                                              "-inform", "PEM",
                                              "-nosmimecap", "-nodetach",
                                              "-nocerts", "-noattr"],
                                             stdin=subprocess.PIPE,
                                             stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE)
        output, err = process.communicate(cms_token)
        retcode = process.poll()
        if retcode:
            raise
        token_info = json.loads(output)
        #print json.dumps(token_info, sort_keys=True,
        #          indent=4, separators=(',', ': '))
        res = {'username': str(token_info['access']['user']['username']),
               'groups': [str(role['name']) for role in token_info['access']['user']['roles']]}
        return res


    def requestAvatarId(self, token):
        # validate credential signature
        token_info = None
        try:
            token_info = self.validate_and_parse_keystone_token(token)
            log.info('Successful login with Keystone token, extracted data: %s' % token_info)
            log.debug('Token: %s' % token)
        except Exception, e:
            log.debug('Exception while validating Keystone token', exc_info=True)
            log.warning(' Authentication failed with Keystone token')
            return defer.fail(UnauthorizedLogin('Invalid credentials'))

        # extract avatar info from the token
        auth = getUtility(IAuthentication)
        oms_user = User(token_info['username'])
        # extract group information from the token
        oms_user.groups.extend(token_info['groups'])
        log.debug('Adding user groups: %s' % ', '.join(token_info['groups']))
        for g in oms_user.groups:
            auth.registerPrincipal(Group(g))
        auth.registerPrincipal(oms_user)
        return defer.succeed(token_info['username'])


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
    salt = decode(encoded_password[6:])[20:]
    h = hashlib.sha1(password)
    h.update(salt)
    return "{SSHA}" + encode(h.digest() + salt).rstrip()


def checkers():
    global _checkers
    if _checkers is None:
        pam_checker = PamAuthChecker() if get_config().getboolean('auth', 'use_pam', False) else None
        password_checker = FilePasswordDB(get_config().get('auth', 'passwd_file'), hash=ssha_hash)
        pubkey_checker = (InMemoryPublicKeyCheckerDontUse()
                          if get_config().getboolean('auth', 'use_inmemory_pkcheck', False) else None)
        _checkers = filter(None, [pam_checker, password_checker, pubkey_checker])
    return _checkers


def setup_conf_reload_watch(path, handler):
    """Registers a inotify watch which will invoke `handler` for passing the open file"""

    def delayed_handler(self, filepath, mask):
        time.sleep(1)
        handler(filepath.open())

    if _platform == "linux" or _platform == "linux2":
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
        log.info("Groups file doesn't exist, generating a default groups file, "
                 "use `bin/groups` to customize it")
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
        print "please set up at least one admin account with `bin/omspasswd`, e.g:"
        print
        print "  <OMS_ROOT>/bin/omspasswd -a john -g admins"
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
        assert type(self._obj) is Proxy

    def __enter__(self):
        _checker = getChecker(self._obj)
        self.previous_interaction = _checker.interaction
        _checker.interaction = new_interaction('root')
        return self._obj

    def __exit__(self, *args):
        getChecker(self._obj).interaction = self.previous_interaction


def sudo(obj):
    """ System utility to elevate privileges to certain object accesses """
    obj = getObject(obj) if type(obj) is Proxy else obj
    return checker.proxy_factory(obj, new_interaction('root'))
