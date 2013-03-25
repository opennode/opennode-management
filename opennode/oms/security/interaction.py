import inspect

from zope.authentication.interfaces import IAuthentication
from zope.component import getUtility
from zope.security._definitions import thread_local
from zope.security.interfaces import IPrincipal
from zope.securitypolicy.interfaces import Allow, Deny, Unset
from zope.securitypolicy.interfaces import IRolePermissionMap
from zope.securitypolicy.interfaces import IPrincipalRoleMap
from zope.securitypolicy.interfaces import IPrincipalPermissionMap
from zope.securitypolicy.zopepolicy import ZopeSecurityPolicy

from zope.securitypolicy.principalpermission import principalPermissionManager
globalPrincipalPermissionSetting = principalPermissionManager.getSetting

from zope.securitypolicy.rolepermission import rolePermissionManager
globalRolesForPermission = rolePermissionManager.getRolesForPermission

from zope.securitypolicy.principalrole import principalRoleManager
globalRolesForPrincipal = principalRoleManager.getRolesForPrincipal

SettingAsBoolean = {Allow: True, Deny: False, Unset: None, None: None}


class OmsSecurityPolicy(ZopeSecurityPolicy):
    """A Security Policy represents an interaction with a principal
    and performs the actual checks.

    The default zope security system depends on keeping the current interaction
    in a thread local variable. OMS is based on the twisted async model and thus
    we avoid setting the current interaction within the current thread, as it could
    be used by different callbacks in the reactor.

    We rely on a custom checker (see opennode.oms.security.checker) for embedding the
    interaction inside the security proxy itself; however in some cases we need to
    use security proxies which are created by other libraries (like secured adapters
    created for IPrincipalRoleManager) and in these cases we need to temporarily setup
    an interaction for the current thread, but we have to prevent it from leaking out to
    other coroutines.

    For that end, we extend ZopeSecurityPolicy in such a way that it can be used as:

    >>> with interaction:
    ...    primrole = IPrincipalRoleManager(obj)
    ...    primrole.getRolesForPrincipal(id)
    ...    # ...

    The `with` context guard will ensure that the function containing this construct
    is not a generator, because using it in a defer.inlineCallbacks method will result
    in leaking the interaction to other goroutines.

    Bypasses parent traversal and applies only global and strictly object-local permissions
    """
    def __enter__(self):
        frame = inspect.getouterframes(inspect.currentframe())[1][0]
        if frame.f_code.co_flags & 0x20:
            raise Exception("Cannot use thread based security interaction while in a generator")

        thread_local.interaction = self

    def __exit__(self, *args):
        del thread_local.interaction

    def cached_prinper(self, parent, principal, groups, permission):
        cache = self.cache(parent)
        try:
            cache_prin = cache.prin
        except AttributeError:
            cache_prin = cache.prin = {}

        cache_prin_per = cache_prin.get(principal)
        if not cache_prin_per:
            cache_prin_per = cache_prin[principal] = {}

        try:
            return cache_prin_per[permission]
        except KeyError:
            pass

        if parent is None:
            prinper = SettingAsBoolean[
                globalPrincipalPermissionSetting(permission, principal, None)]
            cache_prin_per[permission] = prinper
            return prinper

        prinper = IPrincipalPermissionMap(parent, None)
        if prinper is not None:
            prinper = SettingAsBoolean[
                prinper.getSetting(permission, principal, None)]
            if prinper is not None:
                cache_prin_per[permission] = prinper
                return prinper

        prinper = SettingAsBoolean[
            globalPrincipalPermissionSetting(permission, principal, None)]
        cache_prin_per[permission] = prinper
        return prinper

    def cached_roles(self, parent, permission):
        cache = self.cache(parent)
        try:
            cache_roles = cache.roles
        except AttributeError:
            cache_roles = cache.roles = {}
        try:
            return cache_roles[permission]
        except KeyError:
            pass

        roles = dict(
            [(role, 1)
             for (role, setting) in globalRolesForPermission(permission)
             if setting is Allow])

        roleper = IRolePermissionMap(parent, None)
        if roleper:
            for role, setting in roleper.getRolesForPermission(permission):
                if setting is Allow:
                    roles[role] = 1
                elif role in roles:
                    del roles[role]

        cache_roles[permission] = roles
        return roles

    def cached_principal_roles(self, parent, principal):
        cache = self.cache(parent)
        try:
            cache_principal_roles = cache.principal_roles
        except AttributeError:
            cache_principal_roles = cache.principal_roles = {}
        try:
            return cache_principal_roles[principal]
        except KeyError:
            pass

        roles = dict(
            [(role, SettingAsBoolean[setting])
             for (role, setting) in globalRolesForPrincipal(principal)])
        roles['zope.Anonymous'] = True  # Everybody has Anonymous

        prinrole = IPrincipalRoleMap(parent, None)
        if prinrole:
            for role, setting in prinrole.getRolesForPrincipal(principal):
                roles[role] = SettingAsBoolean[setting]

        cache_principal_roles[principal] = roles
        return roles


class SessionStub(object):
    def __init__(self, principal=None):
        self.principal = principal
        self.interaction = None


def new_interaction(principal):
    if not IPrincipal.providedBy(principal):
        auth = getUtility(IAuthentication, context=None)
        principal = auth.getPrincipal(principal)

    interaction = OmsSecurityPolicy()
    interaction.add(SessionStub(principal))
    return interaction
