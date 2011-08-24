import unittest

from nose.tools import eq_, assert_raises
from zope.authentication.interfaces import IAuthentication, PrincipalLookupError
from zope.component import provideUtility, getUtility
from zope.interface import implements
from zope.security.interfaces import Unauthorized, ForbiddenAttribute
from zope.securitypolicy.principalpermission import principalPermissionManager as prinperG
from zope.securitypolicy.zopepolicy import ZopeSecurityPolicy

from opennode.oms.model.model.compute import Compute
from opennode.oms.security.checker import proxy_factory
from opennode.oms.security.principals import User
from opennode.oms.tests.util import run_in_reactor


class SessionStub(object):

    def __init__(self, principal=None):
        self.principal = principal
        self.interaction = None


class DummyAuthenticationUtility:
    implements(IAuthentication)

    def getPrincipal(self, id):
         if id == 'marko':
             return User(id)
         elif id == 'erik':
             return User(id)
         raise PrincipalLookupError(id)

provideUtility(DummyAuthenticationUtility())


class SecurityTestCase(unittest.TestCase):

    def _get_interaction(self, uid):
        auth = getUtility(IAuthentication, context=None)

        interaction = ZopeSecurityPolicy()
        sess = SessionStub(auth.getPrincipal(uid))
        interaction.add(sess)
        return interaction

    def make_compute(self, hostname=u'tux-for-test', state=u'active', memory=2000):
        res = Compute(hostname, state, memory)
        res.architecture = 'linux'
        return res

    @run_in_reactor
    def test_test(self):
        # setup some fake permissions to the test principals
        prinperG.grantPermissionToPrincipal('read', 'marko')
        prinperG.grantPermissionToPrincipal('zope.Nothing', 'erik')

        # set up interactions
        interaction_marko = self._get_interaction('marko')
        interaction_erik = self._get_interaction('erik')

        # get the object being secured
        compute = self.make_compute()
        eq_(compute.architecture, 'linux')

        # get the proxies for the corresponding interactions
        compute_proxy_marko = proxy_factory(compute, interaction_marko)
        compute_proxy_erik = proxy_factory(compute, interaction_erik)


        # check an authorized access
        eq_(compute_proxy_marko.architecture, 'linux')

        # check an unauthorized access
        with assert_raises(Unauthorized):
            eq_(compute_proxy_erik.architecture, 'linux')


        # check a default unauthorized access
        with assert_raises(ForbiddenAttribute):
            eq_(compute_proxy_marko.state, 'active')
