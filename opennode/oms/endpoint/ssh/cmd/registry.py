from .base import Cmd


_commands = {}

def commands():
    """A map of command names to command objects."""
    return _commands


def get_command(name):
    """Returns the command class for a given name.

    Returns NoCommand if the name is empty.
    Returns UnknownCommand if the command does not exist.

    """

    # TODO: Is this approach needed as opposed to handling it
    # upstream? Is this a result of over engineering?
    class UndefinedCommand(Cmd):
        def __call__(self, *args):
            self.terminal.write("No such command: %s\n" % name)

            def dist(a, b):
                return len(set(a) ^ set(b))
            candidates = [v for v in _commands.keys() if dist(name, v) < 4 and v]
            if len(name) > 2 and candidates:
                self.terminal.write("Do you mean '%s'?\n" % min(candidates, key=lambda v: dist(name, v)))

    UndefinedCommand.name = name

    return _commands.get(name, UndefinedCommand)
