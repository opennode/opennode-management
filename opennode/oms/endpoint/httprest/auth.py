import json
import hmac
import logging
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
from opennode.oms.security.authentication import checkers, KeystoneChecker
from opennode.oms.util import blocking_yield


log = logging.getLogger(__name__)


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
        # Overwrite cookies and headers to avoid duplication, see OMS-101.
        # Note, the implementation is somewhat hackish.
        request.cookies = [cookie for cookie in request.cookies if not cookie.startswith('oms_auth_token')]
        request.addCookie('oms_auth_token', token, path='/')

        if request.responseHeaders.hasHeader('X-OMS-Security-Token'):
            request.responseHeaders.removeHeader('X-OMS-Security-Token')

        request.responseHeaders.addRawHeader('X-OMS-Security-Token', token)

    def get_basic_auth_credentials(self, request):
        basic_auth = request.requestHeaders.getRawHeaders('Authorization', [None])[0]
        if basic_auth:
            bc = BasicCredentialFactory(self.realm)
            try:
                return bc.decode(basic_auth.split(' ')[1], None)
            except:
                raise BadRequest("The Authorization header was not parsable")

    def get_keystone_auth_credentials(self, request):
        keystone_token = request.requestHeaders.getRawHeaders('X-Auth-Token', [None])[0]
        log.info('Detected keystone token')
        log.debug('Token: %s' % keystone_token)
        return keystone_token

    @defer.inlineCallbacks
    def authenticate(self, request, credentials, basic_auth=False):
        avatar = None
        if credentials:
            for i in checkers():
                try:
                    log.debug('Authenticating using %s on %s' % (i, credentials.username))
                    avatar = yield i.requestAvatarId(credentials)
                    log.debug('Authentication successful using %s on %s!' % (i, credentials.username))
                    break
                except UnauthorizedLogin:
                    log.warning('Authentication failed with %s on %s!' % (i, credentials.username))

        if avatar:
            # XXX: Can replace with renew_token or vice versa
            token = self.generate_token(credentials)
            self.emit_token(request, token)
            defer.returnValue({'status': 'success', 'token': token})
        else:
            # XXX: Not composable
            if basic_auth:
                raise Unauthorized({'status': 'failed'})
            else:
                raise Forbidden({'status': 'failed'})

    @defer.inlineCallbacks
    def authenticate_keystone(self, request, keystone_token):
        log.debug('Keystone token: %s' % keystone_token)
        avatar = None
        try:
            # avatar will be username from the keystone token info
            avatar = yield KeystoneChecker().requestAvatarId(keystone_token)
        except UnauthorizedLogin:
            log.warning('Authentication failed with Keystone token')
            log.debug('Token: %s' % keystone_token, exc_info=True)
            
        if avatar:
            # emulate OMS behaviour - to allow switchover to OMS-based clients
            token = self._generate_token(avatar)
            self.emit_token(request, token)
            defer.returnValue({'status': 'success', 'token': token})
        else:
            raise Unauthorized({'status': 'failed'})

    def generate_token(self, credentials):
        return self._generate_token(credentials.username)

    def _generate_token(self, username):
        # TODO: register sessions
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
            raise Forbidden("Expired authentication token (%s s ago)" %
                            (time.time() - int(timestamp) / 1000.0))

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
        log.info('Incoming authentication request from %s' % request.getClientIP())
        authentication_utility = getUtility(IHttpRestAuthenticationUtility)

        # enable basic auth only if explicitly requested
        basic_auth = request.args.get('basic_auth', [self.BASIC_AUTH_DEFAULT])[0] != 'false'

        body = request.content.getvalue()

        if request.args.get('username') and request.args.get('password'):
            credentials = UsernamePassword(request.args.get('username')[0],
                                           request.args.get('password')[0])
        elif body:
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
