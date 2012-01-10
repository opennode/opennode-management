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


def grok_all():
    from grokcore.component.testing import grok

    # we have first to load grokkers
    # and then regrok the whole package

    grok('grokcore.security.meta')

    grok('opennode.oms.security.grokkers')
    grok('opennode.oms.endpoint.ssh.cmd.grokkers')
    grok('opennode.oms.endpoint.httprest.grokkers')
    grok('opennode.oms.model.model.actions')

    grok('opennode.oms')

def setup_environ():
    grok_all()
    handle(ApplicationInitalizedEvent())
