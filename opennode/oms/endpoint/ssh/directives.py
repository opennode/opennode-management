import martian
from opennode.oms.endpoint.ssh.cmd import Cmd
from opennode.oms.endpoint.ssh.cmd import commands


__all__ = ['command', 'alias']


class command(martian.Directive):
    """Use this directive in a class in order to set it's command name.
    Only classes marked with this directive will be valid commands.

    """

    scope = martian.CLASS
    store = martian.ONCE
    default = None


class alias(martian.Directive):
    """Use this directive in a class in order to add an alias.
    TODO: make it work with multiple aliases.

    """

    scope = martian.CLASS
    store = martian.ONCE
    default = None


class CmdGrokker(martian.ClassGrokker):
     martian.component(Cmd)
     martian.directive(command)

     def execute(self, class_, command, **kw):
         if command is None:
             return False

         commands()[command] = class_
         class_.name = command
         return True


class AliasGrokker(martian.ClassGrokker):
     martian.component(Cmd)
     martian.directive(alias)

     def execute(self, class_, alias, **kwargs):

         if not getattr(class_, 'aliases', None):
             class_.aliases = []

         if alias:
             class_.aliases.append(alias)
             commands()[alias] = class_

         return False
