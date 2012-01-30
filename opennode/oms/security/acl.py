from zope.component import provideAdapter
from zope.component.security import securityAdapterFactory
from zope.securitypolicy.interfaces import IPrincipalRoleManager
from zope.securitypolicy.principalrole import AnnotationPrincipalRoleManager

from opennode.oms.model.model.base import Model
from opennode.oms.security.directives import permissions
from zope.annotation import IAnnotations


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

    def removeRoleFromPrincipalPath(self, role, principal, path):
        self.removeRoleFromPrincipal(role, principal)
        self._set_path(role, principal, path)

    def assignRoleToPrincipalPath(self, role, principal, path):
        self.assignRoleToPrincipal(role, principal)
        self._set_path(role, principal, path)

    def unsetRoleForPrincipalPath(self, role, principal, path):
        self.unsetRoleForPrincipal(role, principal)
        self._set_path(role, principal, path)

    def _set_path(self, role, principal, path):
        if self.map is None:
            annotations = IAnnotations(self._context)
            map = annotations.get(self.key)
            self.map = map

        if not hasattr(self.map, 'path'):
            self.map.path = {}
        self.map.path[(role, principal)] = path
        self._changed()


provideAdapter(securityAdapterFactory(AclManager, 'zope.Security', False, True), adapts=(Model,), provides=IPrincipalRoleManager)
