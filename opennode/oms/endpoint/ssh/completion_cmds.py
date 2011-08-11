from grokcore.component import baseclass, context
from zope.component import provideSubscriptionAdapter

from opennode.oms.endpoint.ssh import cmd
from opennode.oms.endpoint.ssh.completion import Completer
from opennode.oms.model.model.base import IContainer


class CommandCompleter(Completer):
    """Completes a command."""

    context(type(None))

    def complete(self, token):
        return [name for name in cmd.commands().keys() if name.startswith(token)]


class PathCompleter(Completer):
    """Completes a path name."""
    baseclass()

    def complete(self, token):
        obj = self.context.current_obj
        if IContainer.providedBy(obj):
            return [name for name in obj.listnames() if name.startswith(token)]

        return []


# TODO: move to handler
for command in [cmd.cmd_ls, cmd.cmd_cd, cmd.cmd_cat, cmd.cmd_set]:
    provideSubscriptionAdapter(PathCompleter, adapts=[command])
