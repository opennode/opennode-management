import martian

from opennode.oms.endpoint.ssh.cmd import registry
from opennode.oms.endpoint.ssh.cmd.base import Cmd
from opennode.oms.endpoint.ssh.cmd.directives import command, alias


class CmdGrokker(martian.ClassGrokker):
    martian.component(Cmd)
    martian.directive(command)

    def execute(self, class_, command, **kw):
        if command is None:
            return False

        registry.commands()[command] = class_
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
            registry.commands()[alias] = class_

        return False
