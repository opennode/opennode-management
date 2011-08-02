"""
OpenNode Management Service.
"""
from twisted.internet.defer import Deferred


def deferred_call(self, fun):
    if fun.__name__ == 'on_success':
        return self.addCallback(fun)
    elif fun.__name__ == 'on_error':
        return self.addErrback(fun)
    else:
        raise TypeError("Callable name needs to be either 'on_success' or 'on_error'")
Deferred.__call__ = deferred_call


def discover_adapters():
    from grokcore.component.testing import grok
    grok('opennode.oms.model.location')
    grok('opennode.oms.model.traverser')
    grok('opennode.oms.endpoint.httprest.view')
