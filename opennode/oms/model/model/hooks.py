from logging import DEBUG
from twisted.internet import defer
from twisted.python import log
from zope.component import getUtilitiesFor
from zope.interface import Interface
from zope.interface.interfaces import ComponentLookupError


class IPreValidateHook(Interface):
    """ GlobalUtility interface for performing pre-execute checks on model changes and cancelling them,
    when any of the checks fail """

    def apply(self):
        """ Perform the pre-validate check """

    def applicable(self, context):
        """ Check if context is applicable for this utility """


class PreValidateHookMixin(object):

    context = None

    def __init__(self, context=None):
        self.context = context

    @defer.inlineCallbacks
    def validate_hook(self, principal):
        """
        Calls a global utility that may throw an exception to prevent the current action from starting.
        """
        try:
            checks = getUtilitiesFor(IPreValidateHook)
        except ComponentLookupError:
            log.msg('No pre-validate-hooks (%s)' % (self.context, type(self).__name__),
                    logLevel=DEBUG, system='validate-hook')
        else:
            for name, check in checks:
                if check.applicable(self.context):
                    log.msg('Executing pre-validate-hook %s for %s' % (name, self.context),
                            logLevel=DEBUG, system='validate-hook')
                    yield defer.maybeDeferred(check.apply, principal)
