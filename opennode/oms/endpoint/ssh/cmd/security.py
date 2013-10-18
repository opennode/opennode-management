import collections
import functools
import logging
import os
import transaction

from grokcore.component import implements
from twisted.internet import defer
from zope.authentication.interfaces import IAuthentication
from zope.component import getUtility
from zope.securitypolicy.interfaces import IPrincipalRoleManager
from zope.securitypolicy.rolepermission import rolePermissionManager
from zope.securitypolicy.principalrole import principalRoleManager as prinroleG

from opennode.oms.endpoint.ssh.cmd.base import Cmd
from opennode.oms.endpoint.ssh.cmd.directives import command
from opennode.oms.endpoint.ssh.cmdline import ICmdArgumentsSyntax, VirtualConsoleArgumentParser
from opennode.oms.endpoint.ssh.cmdline import MergeListAction
from opennode.oms.model.model.base import IContainer
from opennode.oms.model.model.symlink import follow_symlinks
from opennode.oms.model.traversal import canonical_path
from opennode.oms.security.acl import NoSuchPermission
from opennode.oms.security.checker import proxy_factory
from opennode.oms.security.passwd import add_user, update_passwd, UserManagementError
from opennode.oms.security.permissions import Role
from opennode.oms.security.principals import User, Group, effective_principals
from opennode.oms.zodb import db


log = logging.getLogger(__name__)


def require_admins_or_same_user(f):
    @functools.wraps(f)
    def _require_admins_or_same_user(self, args):
        principals = map(lambda p: p.id, effective_principals(self.user))

        if args.u not in (None, self.user.id) and 'admins' not in principals:
            self.write('Permission denied: admins not in effective permissions: %s\n'
                       % ', '.join(principals))
            return

        return f(self, args)
    return _require_admins_or_same_user


def require_admins_only(f):
    @functools.wraps(f)
    def _require_admins_only(self, args):
        principals = map(lambda p: p.id, effective_principals(self.user))

        if 'admins' not in principals:
            self.write('Permission denied: admins not in effective permissions: %s\n'
                       % ', '.join(principals))
            return

        return f(self, args)
    return _require_admins_only


def require_admins_only_action(f):
    @functools.wraps(f)
    def _require_admins_only_action(self, cmd, args):
        principals = map(lambda p: p.id, effective_principals(cmd.user))

        if 'admins' not in principals:
            cmd.write('Permission denied: admins not in effective permissions: %s\n'
                       % ', '.join(principals))
            return

        return f(self, cmd, args)
    return _require_admins_only_action


def require_admins(allow_same_user=False):
    if not allow_same_user:
        return require_admins_only
    else:
        return require_admins_or_same_user


class WhoAmICmd(Cmd):
    command('whoami')

    def execute(self, args):
        self.write("%s\n" % self.protocol.principal.id)


def effective_perms(interaction, obj):

    def roles_for(role_manager, obj):
        allowed = []
        for g in effective_principals(interaction):
            for role, setting in role_manager.getRolesForPrincipal(g.id):
                if setting.getName() == 'Allow':
                    allowed.append(role)
        return allowed

    effective_allowed = roles_for(prinroleG, obj)

    with interaction:
        effective_allowed.extend(roles_for(IPrincipalRoleManager(obj), obj))

    return effective_allowed


def pretty_effective_perms(interaction, obj):
    perms = effective_perms(interaction, obj)
    return ''.join(i if Role.nick_to_role[i].id in perms else '-' for i in sorted(Role.nick_to_role.keys()))


class PermCheckCmd(Cmd):
    implements(ICmdArgumentsSyntax)

    command('permcheck')

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('path')

        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('-p', action='store_true', help="Show effective permissions for a given object")
        group.add_argument('-r', action=MergeListAction,
                           help="Check if the user has some rights on a given object")
        return parser

    @db.ro_transact
    def execute(self, args):
        obj = self.traverse(args.path)
        if not obj:
            self.write("No such object %s\n" % args.path)
            return

        if args.p:
            self.write("Effective permissions: %s\n" %
                       pretty_effective_perms(self.protocol.interaction, obj))
        elif args.r:
            self.check_rights(obj, args)

    def check_rights(self, obj, args):
        interaction = self.protocol.interaction
        obj = proxy_factory(obj, interaction)

        allowed = []
        denied = []
        for r in args.r:
            for i in r.split(','):
                i = i.strip()
                if i.startswith('@'):
                    i = i[1:]
                (allowed if interaction.checkPermission(i, obj) else denied).append(i)

        self.write("+%s:-%s\n" % (','.join('@' + i for i in allowed), ','.join('@' + i for i in denied)))


class GetAclCmd(Cmd):
    implements(ICmdArgumentsSyntax)

    command('getfacl')

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('paths', nargs='+')
        parser.add_argument('-v', action='store_true', help='Show grants for every permission')
        parser.add_argument('-R', '--recursive', action='store_true', help='Print permissions recursively')
        return parser

    @db.ro_transact
    def execute(self, args):
        for path in args.paths:
            obj = self.traverse(path)
            if not obj:
                self.write("No such object %s\n" % path)
                continue

            self._do_print_acl(obj, args.v, args.recursive, [obj])

    def _do_print_acl(self, obj, verbose, recursive, seen):
        prinrole = IPrincipalRoleManager(obj)
        auth = getUtility(IAuthentication, context=None)

        user_allow = collections.defaultdict(list)
        user_deny = collections.defaultdict(list)
        users = set()
        for role, principal, setting in prinrole.getPrincipalsAndRoles():
            users.add(principal)
            if setting.getName() == 'Allow':
                user_allow[principal].append(role)
            else:
                user_deny[principal].append(role)

        for principal in users:
            def formatted_perms(perms):
                prin = auth.getPrincipal(principal)
                typ = 'group' if isinstance(prin, Group) else 'user'
                if verbose:
                    def grants(i):
                        return ','.join('@%s' % i[0] for i in rolePermissionManager.getPermissionsForRole(i)
                                        if i[0] != 'oms.nothing')
                    return (typ, principal, ''.join('%s{%s}' %
                                                    (Role.role_to_nick.get(i, '(%s)' % i), grants(i))
                                                    for i in sorted(perms)))
                else:
                    return (typ, principal, ''.join(Role.role_to_nick.get(i, '(%s)' % i)
                                                    for i in sorted(perms)))

            if principal in user_allow:
                self.write("%s:%s:+%s\n" % formatted_perms(user_allow[principal]))
            if principal in user_deny:
                self.write("%s:%s:-%s\n" % formatted_perms(user_deny[principal]))

        if recursive and IContainer.providedBy(follow_symlinks(obj)):
            for sobj in follow_symlinks(obj).listcontent():
                if follow_symlinks(sobj) not in seen:
                    seen.append(sobj)
                    self.write('%s:\n' % canonical_path(sobj))
                    self._do_print_acl(sobj, verbose, recursive, seen)


class SetAclMixin(object):

    def set_acl(self, obj, inherit, allow_perms, deny_perms, del_perms, recursive=False):
        prinrole = IPrincipalRoleManager(obj)
        auth = getUtility(IAuthentication, context=None)
        obj.inherit_permissions = inherit

        def mod_perm(what, setter, p):
            kind, principal, perms = p.split(':')
            if not perms:
                return

            prin = auth.getPrincipal(principal)
            if isinstance(prin, Group) and kind == 'u':
                self.write("No such user '%s', it's a group, perhaps you mean 'g:%s:%s'\n" %
                           (principal, principal, perms))
                return
            elif type(prin) is User and kind == 'g':
                self.write("No such group '%s', it's a user (%s), perhaps you mean 'u:%s:%s'\n" %
                           (principal, prin, principal, perms))
                return

            for perm in perms.strip():
                if perm not in Role.nick_to_role:
                    raise NoSuchPermission(perm)
                role = Role.nick_to_role[perm].id
                self.write("%s permission '%s', principal '%s'\n" % (what, role, principal))
                setter(role, principal)

        def apply_perms(prinrole):
            for p in allow_perms or []:
                mod_perm("Allowing", prinrole.assignRoleToPrincipal, p)

            for p in deny_perms or []:
                mod_perm("Denying", prinrole.removeRoleFromPrincipal, p)

            for p in del_perms or []:
                mod_perm("Unsetting", prinrole.unsetRoleForPrincipal, p)

        apply_perms(prinrole)

        seen = [obj]
        if recursive and IContainer.providedBy(obj):
            for sobj in obj.listcontent():
                if follow_symlinks(sobj) not in seen:
                    prinrole = IPrincipalRoleManager(sobj)
                    sobj.inherit_permissions = inherit
                    seen.append(follow_symlinks(sobj))
                    apply_perms(prinrole)


class SetAclCmd(Cmd, SetAclMixin):
    implements(ICmdArgumentsSyntax)

    command('setfacl')

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('paths', nargs='+')
        parser.add_argument('-R', '--recursive', action='store_true',
                            help='Apply permissions recursively')

        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('-i', '--inherit', action='store_true',
                           help='Set object to inherit permissions from its parent(s)',
                           default=False)
        group.add_argument('-m', action='append',
                           help="add an Allow ace: {u:[user]:permspec|g:[group]:permspec}")
        group.add_argument('-d', action='append',
                           help="add an Deny ace: {u:[user]:permspec|g:[group]:permspec}")
        group.add_argument('-x', action='append',
                           help="remove an ace: {u:[user]:permspec|g:[group]:permspec}")
        return parser

    @db.transact
    def execute(self, args):
        try:
            for path in args.paths:
                obj = self.traverse(path)
                if obj.__transient__:
                    self.write("Transient object %s always inherits permissions from its parent\n" % path)
                    log.warning("Transient object %s always inherits permissions from its parent", path)
                    continue
                with self.protocol.interaction:
                    self.set_acl(obj, args.inherit, args.m, args.d, args.x, recursive=args.recursive)
        except NoSuchPermission as e:
            self.write("No such permission '%s'\n" % (e.message))
            transaction.abort()


class IdCmd(Cmd):
    implements(ICmdArgumentsSyntax)

    command('id')

    @db.ro_transact(proxy=False)
    def subject(self, args):
        return tuple()

    def _print_user(self, user):
        groups = user.groups
        self.write('user: %s\n'
                   'groups: %s\n'
                   'effective_principals: %s\n' %
                   (user.id,
                    ' '.join(map(str, groups)),
                    ' '.join(map(lambda p: p.id, effective_principals(user)))))

    def arguments(self):
        p = VirtualConsoleArgumentParser()
        principals = map(lambda p: p.id, effective_principals(self.user))
        if 'admins' in principals:
            p.add_argument('-u', '--user', help='Check user by name (admins only)')
        return p

    def execute(self, args):
        principals = map(lambda p: p.id, effective_principals(self.user))

        if 'admins' in principals and getattr(args, 'user', None):
            auth = getUtility(IAuthentication, context=None)
            user = auth.getPrincipal(args.user)
            if not user:
                self.write('User not found: %s\n' % args.user)
            else:
                self._print_user(user)
            return

        interaction = self.protocol.interaction

        if not interaction:
            return self.write('user: oms.anonymous\n')

        for participation in interaction.participations:
            user = participation.principal
            self._print_user(user)


class AddUserCmd(Cmd):
    implements(ICmdArgumentsSyntax)
    command('adduser')

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('user')
        parser.add_argument('password')
        parser.add_argument('-g', help="group(s): comma separated list of "
                            "groups the user belongs to", required=False, default=None)
        parser.add_argument('-i', '--uid', help="user ID", required=False, default=0)
        return parser

    @require_admins_only
    def execute(self, args):
        try:
            add_user(args.user, args.password, group=args.g, uid=args.uid)
        except UserManagementError as e:
            self.write('%s\n' % str(e))


class PasswdCmd(Cmd):
    implements(ICmdArgumentsSyntax)
    command('passwd')

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('password')
        parser.add_argument('-u', help='User name', required=False, default=None)
        parser.add_argument('-g', help="group(s): comma separated list of "
                            "groups the user belongs to", required=False, default=None)
        return parser

    @require_admins_or_same_user
    def execute(self, args):
        try:
            update_passwd(args.u or self.user.id, password=args.password, group=args.g)
        except UserManagementError as e:
            self.write('%s\n' % str(e))


class ChownCmd(Cmd):
    implements(ICmdArgumentsSyntax)
    command('chown')

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('user', help='User name')
        parser.add_argument('paths', nargs='+', help='List of paths')
        parser.add_argument('-R', '--recursive', action='store_true',
                            help='Change ownership recursively', default=False, required=False)
        parser.add_argument('-l', '--limit', type=int, default=5, help='Recursion limit (default=5)')
        parser.add_argument('-q', '--quiet', action='store_true', help='Supress console warnings about '
                            'transient objects')
        return parser

    @require_admins_only
    @defer.inlineCallbacks
    def execute(self, args):
        auth = getUtility(IAuthentication, context=None)
        principal = auth.getPrincipal(args.user)

        if not principal:
            self.write('No such user: %s\n' % (args.user))
            return

        def set_owner(path, level):
            target = self.traverse(path)

            if not target:
                self.write('Not found: %s\n' % path)
                return

            if target.__transient__:
                if not args.quiet:
                    self.write("Transient object %s cannot have its owner changed\n" % path)
                return

            target.__owner__ = principal

            if IContainer.providedBy(target) and args.recursive and level < args.limit:
                for item in target.listcontent():
                    set_owner(os.path.join(path, item.__name__), level + 1)

        @db.transact
        def set_owner_all():
            for path in args.paths:
                set_owner(path, 0)

        yield set_owner_all()
