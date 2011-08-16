from grokcore.component import baseclass, context
from zope.component import provideSubscriptionAdapter

from opennode.oms.endpoint.ssh import cmd
from opennode.oms.endpoint.ssh.completion import Completer
from opennode.oms.model.model.base import IContainer


class CommandCompleter(Completer):
    """Completes a command."""

    context(cmd.NoCommand)

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

class ArgSwitchCompleter(Completer):
    """Completes argument switches based on the argparse grammar exposed for a command"""
    baseclass()

    def complete(self, token):
        if token.startswith("-"):
            parser = self.context.arg_parser()

            options = [option
                       for action_group in parser._action_groups
                       for action in action_group._group_actions
                       for option in action.option_strings
                       if option.startswith(token)]
            return options
        else:
            return []

# TODO: move to handler
for command in [cmd.cmd_ls, cmd.cmd_cd, cmd.cmd_cat, cmd.cmd_set]:
    provideSubscriptionAdapter(PathCompleter, adapts=[command])

for command in [cmd.cmd_ls, cmd.cmd_cd, cmd.cmd_cat, cmd.cmd_set, cmd.cmd_quit]:
    provideSubscriptionAdapter(ArgSwitchCompleter, adapts=[command])
