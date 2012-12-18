import martian


__all__ = ['command', 'alias']


class command(martian.Directive):
    """Use this directive in a class in order to set its command name.
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
