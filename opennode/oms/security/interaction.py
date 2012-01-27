import inspect

from zope.authentication.interfaces import IAuthentication
from zope.component import getUtility
from zope.security._definitions import thread_local
from zope.security.interfaces import IPrincipal
from zope.securitypolicy.zopepolicy import ZopeSecurityPolicy


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
    created for IPrincipalRoleManager) and in that cases we need to temporarily setup
    an interaction for the current thread, but we have to avoid that it leaks out to
    other coroutines.

    For that end, we extend ZopeSecurityPolicy in such a way that it can be used as:

    >>> with interaction:
    ...    primrole = IPrincipalRoleManager(obj)
    ...    primrole.getRolesForPrincipal(id)
    ...    # ...

    The `with` context guard will ensure that the function containing this construct
    is not a generator, because using it in a defer.inlineCallbacks method will result
    in leaking the interaction to other goroutines.

    """
    def __enter__(self):
        frame = inspect.getouterframes(inspect.currentframe())[1][0]
        if frame.f_code.co_flags & 0x20:
            raise Exception("Cannot use thread based security interaction while in a generator")

        thread_local.interaction = self

    def __exit__(self, *args):
        del thread_local.interaction


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
