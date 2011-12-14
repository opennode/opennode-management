from zope.authentication.interfaces import IAuthentication, PrincipalLookupError
from zope.component import provideUtility
from zope.interface import implements
from zope.securitypolicy.principalpermission import principalPermissionManager
from zope.securitypolicy.principalrole import principalRoleManager

from opennode.oms.security.principals import User
from opennode.oms.security.roles import admin


class AuthenticationUtility:
    implements(IAuthentication)

    def getPrincipal(self, id):
        if id == None:
            return User('oms.anonymous')
        else:
            return User(id)

        raise PrincipalLookupError(id)


provideUtility(AuthenticationUtility())

# some fake users
principalPermissionManager.grantPermissionToPrincipal('oms.nothing', 'oms.anonymous')

for i in ['user', 'marko', 'erik', 'ilja']:
    principalRoleManager.assignRoleToPrincipal('admin', i)

