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
        self.write("object principal roles: %s\n" % (prinrole.getPrincipalsAndRoles()))


class SetAclCmd(Cmd):
    implements(ICmdArgumentsSyntax)

    command('setfacl')

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('paths', nargs='+')
        parser.add_argument('-m', action='append')
        return parser

    @db.ro_transact
    def execute(self, args):
        for path in args.paths:
            obj = self.traverse(path)
            self._do_set_acl(obj, args.m)

    def _do_set_acl(self, obj, perms):
        prinrole = IPrincipalRoleManager(obj)

        for p in perms:
            kind, principal, roles = p.split(':')
            for role in roles.split(','):
                role = role.strip()
                if not role:
                    continue

                if role.startswith('+'):
                    if kind == 'a':
                        self.write("Allowing role '%s' to principal %s\n" % (role[1:], principal))
                        prinrole.assignRoleToPrincipal(role[1:], principal)
                    elif kind == 'd':
                        self.write("Denying role '%s' to principal %s\n" % (role[1:], principal))
                        prinrole.removeRoleFromPrincipal(role[1:], principal)
                elif role.startswith('-'):
                    self.write("Unsetting role '%s' from principal %s, kind %s\n" % (role[1:], principal, kind))
                    prinrole.unsetRoleForPrincipal(role[1:], principal)
                else:
                    self.write("Use +role or -role\n")
                    transaction.abort()
                    return

        transaction.commit()
