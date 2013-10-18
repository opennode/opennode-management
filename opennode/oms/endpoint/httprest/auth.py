import json
import logging

from grokcore.component import GlobalUtility, context, name
from grokcore.security import require
from twisted.internet import defer
from twisted.cred.credentials import UsernamePassword
from twisted.cred.error import UnauthorizedLogin
from twisted.web.guard import BasicCredentialFactory
from twisted.python.components import registerAdapter
from twisted.web.server import Session
from zope.component import getUtility
from zope.interface import Interface, implements, Attribute

from opennode.oms.model.model.root import OmsRoot
from opennode.oms.endpoint.httprest.base import HttpRestView
from opennode.oms.endpoint.httprest.root import BadRequest, Unauthorized, Forbidden
from opennode.oms.security.authentication import checkers
from opennode.oms.util import blocking_yield


log = logging.getLogger(__name__)


class ISessionStorage(Interface):
    username = Attribute("A username to be stored in a session object")


class SessionStorage(object):
    implements(ISessionStorage)

    def __init__(self, session, username='oms.anonymous'):
        self.username = username

registerAdapter(SessionStorage, Session, ISessionStorage)


class IHttpRestAuthenticationUtility(Interface):

    def get_basic_auth_credentials(request):
        """Returns basic auth credentials object for a given request, or None"""

    def authenticate(request, credentials, basic_auth=False):
        """Performs authentication, adds response headers in case of success,
        throws HttpStatus exceptions in case of failure. Returns a deferred.

        """
    def get_twisted_session(request):
        """Returns twisted session object for a given request if it's not expired"""


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
                raise BadRequest("The Authorization header was not parsable")

    def get_twisted_session(self, request):
        cookiename = b"_".join([b'TWISTED_SESSION'] + request.sitepath)
        sessionCookie = request.getCookie(cookiename)
        if sessionCookie:
            try:
                session = request.site.getSession(sessionCookie)
            except KeyError:
                return None
            else:
                session.touch()
                return session

    @defer.inlineCallbacks
    def authenticate(self, request, credentials, basic_auth=False):
        if credentials:
            for i in checkers():
                try:
                    log.debug('Authenticating using %s on %s' % (i, credentials.username))
                    avatar = yield i.requestAvatarId(credentials)
                    if avatar:
                        session = request.getSession()
                        ISessionStorage(session).username = credentials.username
                        log.debug('Authentication successful using %s on %s!' % (i, credentials.username))
                        defer.returnValue({'status': 'success'})
                        return
                except UnauthorizedLogin:
                    log.warning('Authentication failed with %s on %s!' % (i, credentials.username))
                    continue
        # Credentials are not provided, still there might be a valid session
        session = self.get_twisted_session(request)
        if session:
            defer.returnValue({'status': 'success'})
            return
        if basic_auth:
            raise Unauthorized({'status': 'failed'})
        else:
            raise Forbidden({'status': 'failed'})


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
                raise BadRequest("The request body is not JSON-parsable")

            # cannot be unicode
            username = str(params['username'])
            password = str(params['password'])

            credentials = UsernamePassword(username, password)
        else:
            credentials = authentication_utility.get_basic_auth_credentials(request)

        # if already authenticated, return success even if the request didn't provide auth credentials
        session = authentication_utility.get_twisted_session(request)
        if not credentials and session:
            log.debug('Authentication successful reusing valid session for %s!' % ISessionStorage(session).username)
            return {'status': 'success'}
        # XXX: refactor HttpRestServer.handle_request so that it's not a db.transact
        # so that we can use a defer.inlineCallback here
        return blocking_yield(authentication_utility.authenticate(request, credentials, basic_auth))


class LogoutView(HttpRestView):
    context(OmsRoot)
    name('logout')

    realm = 'OMS'

    def render_GET(self, request):
        authentication_utility = getUtility(IHttpRestAuthenticationUtility)
        session = authentication_utility.get_twisted_session(request)
        if session:
            session.expire()
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
