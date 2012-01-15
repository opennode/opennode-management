import argparse
import os

from grokcore.component import baseclass, context
from twisted.internet import defer
from zope.component import provideSubscriptionAdapter

from opennode.oms.endpoint.ssh.cmd import commands
from opennode.oms.endpoint.ssh.cmd.completion import Completer
from opennode.oms.endpoint.ssh.cmdline import GroupDictAction
from opennode.oms.model.model.base import IContainer
from opennode.oms.model.model.bin import ICommand
from opennode.oms.model.model.symlink import Symlink, follow_symlinks
from opennode.oms.zodb import db


class PositionalCompleter(Completer):
    """Base class for positional completers."""

    baseclass()

    def expected_action(self, parsed, parser):
        """Currently expected action. It looks at the cardinalities """
        for action_group in parser._action_groups:
            for action in action_group._group_actions:
                # For every positional argument:
                if not action.option_strings:
                    actual = 0
                    maximum = 0

                    # Count how many of them we have already.
                    values = getattr(parsed, action.dest, [])
                    if values == action.default:  # don't count default values
                        values = []
                    if not isinstance(values, list):
                        values = [values]
                    actual += len(values)

                    # And the maximum number of expected occurencies.
                    if action.nargs is None:
                        maximum += 1
                    elif isinstance(action.nargs, int):
                        maximum += action.nargs
                    elif action.nargs == argparse.OPTIONAL:
                        maximum += 1
                    else:
                        maximum = float('inf')

                    if actual < maximum:
                        return action


class PathCompleter(PositionalCompleter):
    """Completes a path name."""
    baseclass()

    @db.ro_transact
    def complete(self, token, parsed, parser, **kwargs):
        # If there is still any positional option to complete:
        if self.expected_action(parsed, parser):
            base_path = os.path.dirname(token)
            container = self.context.traverse(base_path)

            if IContainer.providedBy(container):
                def suffix(obj):
                    if IContainer.providedBy(follow_symlinks(obj)):
                        return '/'
                    elif ICommand.providedBy(follow_symlinks(obj)):
                        return '*'
                    elif isinstance(obj, Symlink):
                        return '@'
                    else:
                        return ''

                def name(obj):
                    return os.path.join(base_path, obj.__name__)

                return [name(obj) + suffix(obj) for obj in container.listcontent() if name(obj).startswith(token)]


class CommandCompleter(PathCompleter):
    """Completes a command."""

    context(commands.NoCommand)

    @defer.inlineCallbacks
    def complete(self, token, parsed, parser, protocol=None, **kwargs):
        cmds = yield self._scan_search_path(protocol)

        # TODO: check that only 'executables' and 'directories' are returned.
        paths = yield super(CommandCompleter, self).complete(token, parsed, parser, **kwargs)

        defer.returnValue([value for value in list(cmds) + list(set(paths).difference(i + '*' for i in cmds)) if value.startswith(token)])

    @db.ro_transact
    def _scan_search_path(self, protocol):
        dummy = commands.NoCommand(protocol)

        cmds = []
        for d in protocol.environment['PATH'].split(':'):
            for i in dummy.traverse(d) or []:
                if ICommand.providedBy(i):
                    cmds.append(i.cmd.name)

        return set(cmds)

    def expected_action(self, parsed, parser):
        return True


class KeywordPathSubCompleter(PathCompleter):
    """
    Implement a FS path completer which works as subcompleter for the keyworded arguments.

    """
    baseclass()

    def __init__(self, context, base_path=''):
        super(KeywordPathSubCompleter, self).__init__(context)
        self.base_path = base_path

    @defer.inlineCallbacks
    def complete(self, token, parsed, parser, **kwargs):
        self.original_context = self.context
        self.context = self
        keyword, value_prefix = token.split('=')
        res = yield super(KeywordPathSubCompleter, self).complete(value_prefix, parsed, parser, **kwargs)
        defer.returnValue([keyword + '=' + i for i in res])

    def traverse(self, path):
        if not os.path.isabs(path):
            path = self.base_path + path
        return self.original_context.traverse(path)

    def expected_action(self, parsed, parser):
        return True


class ArgSwitchCompleter(Completer):
    """Completes argument switches based on the argparse grammar exposed for a command"""
    baseclass()

    def complete(self, token, parsed, parser, **kwargs):
        if token.startswith("-"):
            return [option
                    for action_group in parser._action_groups
                    for action in action_group._group_actions
                    for option in action.option_strings
                    if option.startswith(token) and not self.option_consumed(action, parsed)]

    def option_consumed(self, action, parsed):
        # "count" actions can be repeated
        if action.nargs > 0 or isinstance(action, argparse._CountAction):
            return False

        if isinstance(action, GroupDictAction):
            value = getattr(parsed, action.group, {}).get(action.dest, action.default)
        else:
            value = getattr(parsed, action.dest, action.default)

        return value != action.default


class KeywordSwitchCompleter(ArgSwitchCompleter):
    """Completes key=value argument switches based on the argparse grammar exposed for a command.
    TODO: probably more can be shared with ArgSwitchCompleter."""

    baseclass()

    def complete(self, token, parsed, parser, display=False, **kwargs):
        return [('[%s=]' if display and not action.was_required else '%s=') % (option[1:])
                for action_group in parser._action_groups
                for action in action_group._group_actions
                for option in action.option_strings
                if option.startswith('=' + token) and not self.option_consumed(action, parsed)]


class KeywordValueCompleter(ArgSwitchCompleter):
    """Completes the `value` part of key=value constructs based on the type of the keyword.
    Currently works only for args which declare an explicit enumeration."""

    baseclass()

    def complete(self, token, parsed, parser, **kwargs):
        if '=' in token:
            keyword, value_prefix = token.split('=')

            action = self.find_action(keyword, parsed, parser)
            if isinstance(action, GroupDictAction) and action.is_path:
                subcompleter = KeywordPathSubCompleter(self.context, action.base_path)
                return subcompleter.complete(token, parsed, parser, **kwargs)

            if action.choices:
                return [keyword + '=' + value for value in action.choices if value.startswith(value_prefix)]

        return []

    def find_action(self, keyword, parsed, parser):
        for action_group in parser._action_groups:
            for action in action_group._group_actions:
                if action.dest == keyword:
                    return action


class PositionalChoiceCompleter(PositionalCompleter):
    baseclass()

    def complete(self, token, parsed, parser, **kwargs):
        action = self.expected_action(parsed, parser)
        if action and action.choices:
            return [value for value in action.choices if value.startswith(token)]


class EnvironmentCompleter(Completer):
    baseclass()

    def complete(self, token, parsed, parser, protocol=None, **kwargs):
        return [value for value in protocol.environment.keys() if value.startswith(token)]


# TODO: move to handler
for command in [commands.ListDirContentsCmd, commands.ChangeDirCmd, commands.CatObjectCmd, commands.SetAttrCmd, commands.RemoveCmd, commands.MoveCmd, commands.FileCmd, commands.EchoCmd, commands.LinkCmd, commands.EditCmd]:
    provideSubscriptionAdapter(PathCompleter, adapts=(command, ))

for command in [commands.ListDirContentsCmd, commands.ChangeDirCmd, commands.CatObjectCmd, commands.SetAttrCmd, commands.RemoveCmd, commands.QuitCmd, commands.FileCmd, commands.LinkCmd, commands.KillTaskCmd]:
    provideSubscriptionAdapter(ArgSwitchCompleter, adapts=(command, ))

for command in [commands.SetAttrCmd, commands.CreateObjCmd]:
    provideSubscriptionAdapter(KeywordSwitchCompleter, adapts=(command, ))

for command in [commands.SetAttrCmd, commands.CreateObjCmd]:
    provideSubscriptionAdapter(KeywordValueCompleter, adapts=(command, ))

for command in [commands.HelpCmd, commands.CreateObjCmd]:
    provideSubscriptionAdapter(PositionalChoiceCompleter, adapts=(command, ))

for command in [commands.SetEnvCmd]:
    provideSubscriptionAdapter(EnvironmentCompleter, adapts=(command, ))
