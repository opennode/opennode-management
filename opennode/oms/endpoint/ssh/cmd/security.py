import collections
import transaction

from grokcore.component import implements
from zope.securitypolicy.interfaces import IPrincipalRoleManager

from opennode.oms.endpoint.ssh.cmd.base import Cmd
from opennode.oms.endpoint.ssh.cmd.directives import command
from opennode.oms.endpoint.ssh.cmdline import ICmdArgumentsSyntax, VirtualConsoleArgumentParser
from opennode.oms.zodb import db


class WhoAmICmd(Cmd):
    command('whoami')

    def execute(self, args):
        self.write("%s\n" % self.protocol.principal.id)


class GetAclCmd(Cmd):
    implements(ICmdArgumentsSyntax)

    command('getfacl')

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('paths', nargs='+')
        return parser

    @db.ro_transact
    def execute(self, args):
        for path in args.paths:
            obj = self.traverse(path)
            self._do_print_acl(obj)

    def _do_print_acl(self, obj):
        prinrole = IPrincipalRoleManager(obj)

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
                return (principal, ','.join(sorted(perms)))
            if principal in user_allow:
                self.write("user:%s:+%s\n" % formatted_perms(user_allow[principal]))
            if principal in user_deny:
                self.write("user:%s:-%s\n" % formatted_perms(user_deny[principal]))


class SetAclCmd(Cmd):
    implements(ICmdArgumentsSyntax)

    command('setfacl')

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('paths', nargs='+')
        parser.add_argument('-m', action='append', help="add an Allow ace: {u:[user]:permspec|g:[group]:permspec}")
        parser.add_argument('-d', action='append', help="add an Deny ace: {u:[user]:permspec|g:[group]:permspec}")
        parser.add_argument('-x', action='append', help="remove an ace: {u:[user]:permspec|g:[group]:permspec}")
        return parser

    @db.ro_transact
    def execute(self, args):
        for path in args.paths:
            obj = self.traverse(path)
            self._do_set_acl(obj, args.m, args.d, args.x)

    def _do_set_acl(self, obj, allow_perms, deny_perms, del_perms):
        prinrole = IPrincipalRoleManager(obj)

        def mod_perm(what, setter, p):
            kind, principal, perms = p.split(':')
            for role in perms.split(','):
                role = role.strip()
                if not role:
                    continue

                self.write("%s permission '%s', principal '%s'\n" % (what, role, principal))
                setter(role, principal)

        for p in allow_perms or []:
            mod_perm("Allowing", prinrole.assignRoleToPrincipal, p)

        for p in deny_perms or []:
            mod_perm("Denying", prinrole.removeRoleFromPrincipal, p)

        for p in del_perms or []:
            mod_perm("Unsetting", prinrole.unsetRoleForPrincipal, p)

        transaction.commit()
