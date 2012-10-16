import json
import hmac
import time

from base64 import urlsafe_b64encode as encodestring, urlsafe_b64decode as decodestring
from grokcore.component import GlobalUtility, context, name
from grokcore.security import require
from twisted.internet import defer
from twisted.cred.credentials import UsernamePassword
from twisted.cred.error import UnauthorizedLogin
from twisted.web.guard import BasicCredentialFactory
from zope.component import getUtility
from zope.interface import Interface, implements

from opennode.oms.config import get_config
from opennode.oms.model.model.root import OmsRoot
from opennode.oms.endpoint.httprest.base import HttpRestView
from opennode.oms.endpoint.httprest.root import BadRequest, Unauthorized, Forbidden
from opennode.oms.security.authentication import checkers
from opennode.oms.util import blocking_yield


class IHttpRestAuthenticationUtility(Interface):

    def get_basic_auth_credentials(request):
        """Returns basic auth credentials object for a given request, or None"""

    def authenticate(request, credentials, basic_auth=False):
        """Performs authentication, adds response headers in case of success,
        throws HttpStatus exceptions in case of failure. Returns a deferred.

        """

    # XXX: use a principal instead of the credentials
    def generate_token(self, credentials):
        """Generates a secure token for the given credentials"""

    def get_principal(self, token):
        """Retrieves a principal for a token"""


class HttpRestAuthenticationUtility(GlobalUtility):
    implements(IHttpRestAuthenticationUtility)

    realm = 'OMS'

    token_key = get_config().get('auth', 'token_key')

    def get_token(self, request):
        cookie = request.getCookie('oms_auth_token')
        if cookie:
            return cookie

        header = request.getHeader('X-OMS-Security-Token')
        if header:
            return header

        param = request.args.get('security_token', [None])[0]
        if param:
            return param

    def emit_token(self, request, token):
        request.addCookie('oms_auth_token', token, path='/')
        request.responseHeaders.addRawHeader('X-OMS-Security-Token', token)

    def get_basic_auth_credentials(self, request):
        basic_auth = request.requestHeaders.getRawHeaders('Authorization', [None])[0]
        if basic_auth:
            bc = BasicCredentialFactory(self.realm)
            try:
                return bc.decode(basic_auth.split(' ')[1], None)
            except:
                raise BadRequest("The Authorization header was not parsable")

    @defer.inlineCallbacks
    def authenticate(self, request, credentials, basic_auth=False):
        avatar = None
        if credentials:
            for i in checkers():
                try:
                    avatar = yield i.requestAvatarId(credentials)
                    break
                except UnauthorizedLogin:
                    print 'Unauthorized thrown by', i, 'on', credentials.username
                    continue

        if avatar:
            token = self.generate_token(credentials)
            self.emit_token(request, token)
            defer.returnValue({'status': 'success', 'token': token})
        else:
            if basic_auth:
                raise Unauthorized({'status': 'failed'})
            else:
                raise Forbidden({'status': 'failed'})

    def generate_token(self, credentials):
        return self._generate_token(credentials.username)

    def _generate_token(self, username):
        # XXX: todo real cryptographic token
        head = '%s:%s' % (username, int(time.time() * 1000))
        signature = hmac.new(self.token_key, head).digest()
        return encodestring('%s;%s' % (head, signature)).strip()

    def get_principal(self, token):
        if not token:
            return 'oms.anonymous'

        head, signature = decodestring(token).split(';', 1)
        if signature != hmac.new(self.token_key, head).digest():
            raise Forbidden("Invalid authentication token")

        user, timestamp = head.split(':')
        if int(timestamp) / 1000.0 + get_config().getint('auth', 'token_ttl') < time.time():
            raise Forbidden("Expired authentication token (%s s ago)" % (time.time() - int(timestamp) / 1000.0))

        return user

    def renew_token(self, request, token):
        new_token = self._generate_token(self.get_principal(token))
        self.emit_token(request, new_token)


class AuthView(HttpRestView):
    context(OmsRoot)
    name('auth')
    require('oms.nothing')

    realm = 'OMS'

    BASIC_AUTH_DEFAULT = 'false'

    # Should be render_GET but ONC (i.e. ExtJS) cannot attach a request body to GET requests
    def render(self, request):
        authentication_utility = getUtility(IHttpRestAuthenticationUtility)

        # enable basic auth only if explicitly requested
        basic_auth = request.args.get('basic_auth', [self.BASIC_AUTH_DEFAULT])[0] != 'false'

        body = request.content.getvalue()

        if body:
            try:
                params = json.loads(body)
            except ValueError:
                raise BadRequest("The request body not JSON-parsable")

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

    BASIC_AUTH_DEFAULT = 'true'


class BasicAuthLogoutView(LogoutView):
    context(OmsRoot)
    name('basicauthlogout')
    require('oms.nothing')

    def render_GET(self, request):
        super(BasicAuthLogoutView, self).render_GET(request)
        raise Unauthorized()
