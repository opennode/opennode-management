"""
OpenNode Management Service.
"""

from twisted.internet.defer import Deferred
from zope.component import handle
from zope.interface import Interface,implements


class IApplicationInitializedEvent(Interface):
    """Emitted when application is initialized"""


class ApplicationInitalizedEvent(object):
    implements(IApplicationInitializedEvent)


def deferred_call(self, fun):
    if fun.__name__ == 'on_success':
        return self.addCallback(fun)
    elif fun.__name__ == 'on_error':
        return self.addErrback(fun)
    else:
        raise TypeError("Callable name needs to be either 'on_success' or 'on_error'")
Deferred.__call__ = deferred_call


def setup_environ():
    from grokcore.component.testing import grok
    grok('opennode.oms.endpoint.ssh.cmd.grokkers')  # XXX: Not sure why this needs to be explicit--an ordering issue?
    grok('opennode.oms.model.model.actions')
    grok('opennode.oms.security.grokkers')  # XXX: Not sure why this needs to be explicit--an ordering issue?
    grok('grokcore.security.meta') # invoke the PermissionGrokker which will register groksecurity permissions.
    grok('opennode.oms')

    handle(ApplicationInitalizedEvent())
