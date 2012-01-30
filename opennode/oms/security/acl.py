import re

from zope.annotation import IAnnotations
from zope.component import provideAdapter
from zope.component.security import securityAdapterFactory
from zope.securitypolicy.interfaces import IPrincipalRoleManager
from zope.securitypolicy.principalrole import AnnotationPrincipalRoleManager
from zope.securitypolicy.interfaces import Allow, Deny, Unset

from opennode.oms.model.model.base import Model
from opennode.oms.model.traversal import canonical_path
from opennode.oms.security.directives import permissions
from opennode.oms.security.interaction import current_security_check


def glob_to_regex(pat, dirsep='/'):
    dirsep = re.escape(dirsep)
    regex = (re.escape(pat).replace("\\*\\*" + dirsep, ".*")
                           .replace("\\*\\*", ".*")
                           .replace("\\*", "[^%s]*" % dirsep)
                           .replace("\\?", "[^%s]" % dirsep))
    return re.compile(regex + "$")


class AclManager(AnnotationPrincipalRoleManager):
    """Reimplements the mapping between principals and roles (a.k.a OMS permissions)
    taking into consideration the path declaration for the ACL

    """


    permissions(dict(assignRoleToPrincipal='zope.Security',
                     removeRoleFromPrincipal='zope.Security',
                     unsetRoleForPrincipal='zope.Security',
                     ))

    def __init__(self, context):
        super(AclManager, self).__init__(context)

    def __nonzero__(self):
        return True

    def getRolesForPrincipal(self, principal):
        self._ensure_map()
        if self.map is None:
            return []

        tail = current_security_check.path[len(canonical_path(self.__parent__)) + 1:]

        roles = {}

        for (role, prin), paths in self.map.path.items():
            if prin == principal:
                for path in sorted(paths):
                    if not (tail == '' and path != '') and glob_to_regex(path).match(tail):
                        setting = paths[path]
                        roles[role] = setting

        return roles.items()

    def getPrincipalsAndRoles(self):
        raise NotImplemented("Shouldn't be called")

    def getPrincipalsAndRolesPaths(self):
        for (role, principal), paths in self.map.path.items():
            for path, setting in paths.items():
                yield role, principal, setting, path

    def removeRoleFromPrincipalPath(self, role, principal, path):
        self._set_path(role, principal, path, Deny)

    def assignRoleToPrincipalPath(self, role, principal, path):
        self._set_path(role, principal, path, Allow)

    def unsetRoleForPrincipalPath(self, role, principal, path):
        self._set_path(role, principal, path, Unset)

    def _ensure_map(self):
        if self.map is None:
            annotations = IAnnotations(self._context)
            map = annotations.get(self.key)
            self.map = map

        if self.map is not None and not hasattr(self.map, 'path'):
            self.map.path = {}

    def _set_path(self, role, principal, path, setting):
        self._ensure_map()

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
