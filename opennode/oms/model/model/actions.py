from __future__ import absolute_import

import martian
from grokcore.component import Subscription, baseclass, querySubscriptions
from zope.interface import implements

from .base import IContainerExtender, ReadonlyContainer
from .bin import ICommand, Command


class ActionsContainer(ReadonlyContainer):
    """Implements a dynamic view containing actions that can be performed on a given object.

    """
    __name__ = 'actions'

    def __init__(self, parent):
        self.__parent__ = parent

    def content(self):
        actions = querySubscriptions(self.__parent__, ICommand)
        return dict((i._name, Command(i._name, self, i.cmd)) for i in actions)


class ActionsContainerExtension(Subscription):
    implements(IContainerExtender)
    baseclass()

    def extend(self):
        return {'actions': ActionsContainer(self.context)}


class Action(Subscription):
    implements(ICommand)
    baseclass()

    def subject(self, args):
        return tuple()

class action(martian.Directive):
    """Use this directive on adapters used to define actions for specific model objects."""
    scope = martian.CLASS
    store = martian.ONCE
    default = None


class ActionGrokker(martian.ClassGrokker):
    martian.component(Subscription)
    martian.directive(action)

    def execute(self, class_, action, **kw):
        if action is None:
            return False

        if getattr(class_, 'cmd', None) is None:
            class_.cmd = _action_decorator_parametrized(class_)(class_.execute)
            class_._name = action
        return True


def _action_decorator_parametrized(cls):
    def _action_decorator(fun):
        """
        Decorate a method so that it behaves as a property which returns a Cmd object.
        """
        from opennode.oms.endpoint.ssh.cmd.base import Cmd
        from opennode.oms.endpoint.ssh.cmdline import ICmdArgumentsSyntax, VirtualConsoleArgumentParser
        from opennode.oms.zodb import db
        from opennode.oms.zodb.proxy import make_persistent_proxy

        @property
        def cmd(wself):
            this = wself

            class ActionCmd(Cmd):
                implements(ICmdArgumentsSyntax)
                name = wself._name
                _name = wself._name
                aliases = None
                subject = wself.subject

                def arguments(self):
                    return VirtualConsoleArgumentParser()

                def execute(self, args):
                    # we obtained `this` before the action exited from the db.transact decorator
                    # thus we need to reapply the db proxy
                    this.context = make_persistent_proxy(this.context, db.context(self))
                    return fun(this, self, args)

            if hasattr(cls, 'arguments'):
                def action_arguments(self):
                    return cls.arguments(this)
                ActionCmd.arguments = action_arguments
            return ActionCmd
        return cmd
    return _action_decorator
