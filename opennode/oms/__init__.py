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


def setup_environ():
    from grokcore.component.testing import grok
    grok('opennode.oms.endpoint.ssh.cmd.grokkers')  # XXX: Not sure why this needs to be explicit--an ordering issue?
    grok('opennode.oms')
