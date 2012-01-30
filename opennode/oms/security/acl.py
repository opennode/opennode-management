from zope.annotation import IAnnotations
from zope.component import provideAdapter
from zope.component.security import securityAdapterFactory
from zope.securitypolicy.interfaces import IPrincipalRoleManager
from zope.securitypolicy.principalrole import AnnotationPrincipalRoleManager
from zope.securitypolicy.interfaces import Allow, Deny, Unset

from opennode.oms.model.model.base import Model
from opennode.oms.security.directives import permissions


class AclManager(AnnotationPrincipalRoleManager):
    permissions(dict(assignRoleToPrincipal='zope.Security',
                     removeRoleFromPrincipal='zope.Security',
                     unsetRoleForPrincipal='zope.Security',
                     ))

    def __init__(self, context):
        super(AclManager, self).__init__(context)

    def getRolesForPrincipal(self, principal):
        roles = super(AclManager, self).getRolesForPrincipal(principal)
        return roles

    def getPrincipalsAndRoles(self):
        prinroles = super(AclManager, self).getPrincipalsAndRoles()
        return prinroles

    def getPrincipalsAndRolesPaths(self):
        for (role, principal), paths in self.map.path.items():
            for path, setting in paths.items():
                yield role, principal, setting, path

    def removeRoleFromPrincipalPath(self, role, principal, path):
        self.removeRoleFromPrincipal(role, principal)
        self._set_path(role, principal, path, Deny)

    def assignRoleToPrincipalPath(self, role, principal, path):
        self.assignRoleToPrincipal(role, principal)
        self._set_path(role, principal, path, Allow)

    def unsetRoleForPrincipalPath(self, role, principal, path):
        self.unsetRoleForPrincipal(role, principal)
        self._set_path(role, principal, path, Unset)

    def _set_path(self, role, principal, path, setting):
        if self.map is None:
            annotations = IAnnotations(self._context)
            map = annotations.get(self.key)
            self.map = map

        if not hasattr(self.map, 'path'):
            self.map.path = {}

        key = (role, principal)
        # XXX: check for str is just for backward compat, remove after merge to master
        if key not in self.map.path or isinstance(self.map.path[key], str):
            self.map.path[key] = {}

        if setting is Unset:
            if path in self.map.path[key]:
                del self.map.path[key][path]
        else:
            self.map.path[key][path] = setting

        self._changed()


provideAdapter(securityAdapterFactory(AclManager, 'zope.Security', False, True), adapts=(Model,), provides=IPrincipalRoleManager)
