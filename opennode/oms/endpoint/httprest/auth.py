import json

from grokcore.component import GlobalUtility, context, name
from grokcore.security import require
from twisted.internet import defer
from twisted.cred.credentials import UsernamePassword
from twisted.cred.error import UnauthorizedLogin
from twisted.web.guard import BasicCredentialFactory
from zope.component import getUtility
from zope.interface import Interface, implements

from opennode.oms.model.model.root import OmsRoot
from opennode.oms.endpoint.httprest.base import HttpRestView
from opennode.oms.endpoint.httprest.root import BadRequest, Unauthorized, Forbidden
from opennode.oms.security.authentication import checkers
from opennode.oms.util import blocking_yield


class IHttpRestAuthenticationUtility(Interface):
    def get_basic_auth_credentials(request):
        """Return basic auth credentials object for a given request, or None"""

    def authenticate(request, credentials, basic_auth=False):
        """Perform authentication, adds response headers in case of success,
        throws HttpStatus exceptions in case of failure. Returns a deferred.

        """

    # XXX: use a principal instead of the credentials
    def generate_token(self, credentials):
        """Generate a secure token for the given credentials"""


class HttpRestAuthenticationUtility(GlobalUtility):
    implements(IHttpRestAuthenticationUtility)

    realm = 'OMS'

    def get_basic_auth_credentials(self, request):
        basic_auth = request.requestHeaders.getRawHeaders('Authorization', [None])[0]
        if basic_auth:
            bc = BasicCredentialFactory(self.realm)
            try:
                return bc.decode(basic_auth.split(' ')[1], None)
            except:
                raise BadRequest, "The Authorization header was not parsable"

    @defer.inlineCallbacks
    def authenticate(self, request, credentials, basic_auth=False):
        avatar = None
        if credentials:
            for i in checkers:
                try:
                    avatar = yield i.requestAvatarId(credentials)
                    break
                except UnauthorizedLogin:
                    continue

        if avatar:
            token = self.generate_token(credentials)
            request.addCookie('oms_auth_token', token, path='/')
            defer.returnValue({'status': 'success', 'token': token})
        else:
            if basic_auth:
                raise Unauthorized({'status': 'failed'})
            else:
                raise Forbidden({'status': 'failed'})

    def generate_token(self, credentials):
        # XXX: todo real cryptographic token
        return 'fake_token_%s' % credentials.username


class AuthView(HttpRestView):
    context(OmsRoot)
    name('auth')
    require('oms.nothing')

    realm = 'OMS'

    basic_auth = 'false'

    # Should be render_GET but ONC (i.e. ExtJS) cannot attach a request body to GET requests
    def render(self, request):
        authentication_utility = getUtility(IHttpRestAuthenticationUtility)

        # enable basic auth only if explicitly requested
        basic_auth = request.args.get('basic_auth', [self.basic_auth])[0] != 'false'

        body = request.content.getvalue()

        if body:
            try:
                params = json.loads(body)
            except ValueError:
                raise BadRequest, "The request body not JSON-parsable"

            # cannot be unicode
            username = str(params['username'])
            password = str(params['password'])

            credentials = UsernamePassword(username, password)
        else:
            credentials = authentication_utility.get_basic_auth_credentials(request)

        # if already authenticated, return success even if the request didn't provide auth credentials
        if not credentials and request.interaction.checkPermission('rest', object):
            return {'status': 'success'}

        # XXX: refactor HttpRestServer.handle_request so that it's not a db.transact
        # so that we can use a defer.inlineCallback here
        return blocking_yield(authentication_utility.authenticate(request, credentials, basic_auth))


class LogoutView(HttpRestView):
    context(OmsRoot)
    name('logout')

    realm = 'OMS'

    def render_GET(self, request):
        request.addCookie('oms_auth_token', '', expires='Wed, 01 Jan 2000 00:00:00 GMT')
        return {'status': 'success'}


class BasicAuthView(AuthView):
    context(OmsRoot)
    name('basicauth')
    require('oms.nothing')

    basic_auth = 'true'


class BasicAuthLogoutView(LogoutView):
    context(OmsRoot)
    name('basicauthlogout')
    require('oms.nothing')

    def render_GET(self, request):
        super(BasicAuthLogoutView, self).render_GET(request)
        raise Unauthorized()
