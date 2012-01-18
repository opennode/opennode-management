"""
OpenNode Management Service.
"""

from twisted.internet.defer import Deferred
from zope.component import handle
from zope.interface import Interface, implements


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


def load_zcml(*args):
    """We rely on grok to load the configuration for our modules, but we depend on some libraries which
    have only zcml based configuration, thus we need to load only those we need."""

    from zope.configuration.config import ConfigurationMachine
    from zope.configuration import xmlconfig
    context = ConfigurationMachine()
    xmlconfig.registerCommonDirectives(context)

    for i in args:
        xmlconfig.include(context, 'configure.zcml', context.resolve(i))

    context.execute_actions()


def grok_all():
    from grokcore.component.testing import grok

    load_zcml('zope.securitypolicy', 'zope.annotation')

    grok('grokcore.security.meta')
    grok('grokcore.annotation.meta')

    grok('opennode.oms.security.grokkers')
    grok('opennode.oms.endpoint.ssh.cmd.grokkers')
    grok('opennode.oms.endpoint.httprest.grokkers')
    grok('opennode.oms.model.model.actions')

    grok('opennode.oms')


def setup_environ():
    grok_all()
    handle(ApplicationInitalizedEvent())
