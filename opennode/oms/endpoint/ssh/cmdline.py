import argparse, re

from zope.interface import Interface
from twisted.python import log


class ArgumentParsingError(Exception):

    def __init__(self, status, message=None):
        self.status = status
        self.message = message

    def __str__(self):
        return 'ArgumentParsingError(%s)' % (self.message)


class ArgumentParsingInterrupted(ArgumentParsingError):

    def __init__(self):
        pass

    def __str__(self):
        return 'ArgumentParsingInterrupted()'


class InstrumentableArgumentParser(argparse.ArgumentParser):
    """ArgumentParser subclass that raises an exception instead of exiting in case of errors,
    and allows all output to be redirected to a custom output stream.

    """

    def __init__(self, file=None, *args, **kwargs):
        self.file = file
        super(InstrumentableArgumentParser, self).__init__(*args, **kwargs)

    def _print_message(self, message, file=None):
        """Ensures that the file passed to the parser constructor is the one actually used
        to output the message. Argparse's behavior is to default to stderr.

        """
        return super(InstrumentableArgumentParser, self)._print_message(message, self.file)

    def exit(self, status=0, message=None):
        raise ArgumentParsingInterrupted

    def error(self, message):
        print >>self.file, message
        raise ArgumentParsingError(2, message)


class VirtualConsoleArgumentParser(InstrumentableArgumentParser):
    """This parser avoids using the argparse help action, since it fires during the parsing,
    We want to pospone the handling of help until after the args are parsed.

    """

    def __init__(self, add_help=None, *args, **kwargs):
        super(VirtualConsoleArgumentParser, self).__init__(add_help=False, formatter_class=VirtualConsoleHelpFormatter, *args, **kwargs)

        if add_help:
            self.add_argument('-h', '--help', action=argparse._HelpAction, help="show this help message and exit")

        self.declarations = {}

    def parse_args(self, args=None, namespace=None):
        parsed = super(VirtualConsoleArgumentParser, self).parse_args(args, namespace)

        for dest, default in self.declarations.items():
            if not hasattr(parsed, dest):
                setattr(parsed, dest, default)

        return parsed

    def declare_argument(self, dest, default=None):
        """Declares the existence of an argument without adding a requirement and an option string for it.

        It's useful for GroupDictAction argument or other actions where multiple arguments store in the same value.
        The `dest` attribute for declared arguments will have it's default value even if no argument was defined
        or matched.

        """
        self.declarations[dest] = default


class PartialVirtualConsoleArgumentParser(VirtualConsoleArgumentParser):
    """Use this if you want to avoid printing error messages and retry on partial arglists."""

    def __init__(self, file=None, add_help=None, *args, **kwargs):
        """Explicitly puts to false the add_help and uses a 'dev/null' output."""
        class DevNull(object):
            def write(self, *_):
                pass

        super(PartialVirtualConsoleArgumentParser, self).__init__(file=DevNull(), *args, **kwargs)

        if add_help:
            self.add_argument('-h', '--help', action='store_true', help="show this help message and exit")

    def parse_args(self, args=None, namespace=None):
        try:
            # remove required parameters during partial parsing
            for action_group in self._action_groups:
                for action in action_group._group_actions:
                    action.was_required = action.required
                    action.required = False

            # yes, skip our direct parent
            return super(VirtualConsoleArgumentParser, self).parse_args(args, namespace)
        except ArgumentParsingError:
            try:
                return super(VirtualConsoleArgumentParser, self).parse_args(args[:-1], namespace)
            except ArgumentParsingError as e:
                # give up, probably we have mandatory positional args
                log.msg("Tried hard but cannot parse %s" % e)
                return object()  # Empty parse results.


class VirtualConsoleHelpFormatter(argparse.HelpFormatter):
    """Takes care of presenting our special keyworded options in their canonical key = value form."""

    def format_help(self):
        help = super(VirtualConsoleHelpFormatter, self).format_help()
        return re.sub(r'=(\w*)', r'\1 =', help)


class GroupDictAction(argparse.Action):
    """Extends argparser with an action suited for key=value keyword arguments.
    Each arg declared with a KeywordAction, will be put inside a dictionary
    (by default called `keywords`) inside the resulting arg object.

    This is particularly useful if you have a number of dynamically defined args
    which would otherwise end up in cluttering the resulting arg object without
    a clear way to enumerate them all.

    You can override this grouping with the `group` parameter.

    """

    def __init__(self, group='group', **kwargs):
        super(GroupDictAction, self).__init__(**kwargs)
        self.group = group

    def __call__(self, parser, namespace, values, option_string=None):
        group = getattr(namespace, self.group, {})
        group[self.dest] = values
        setattr(namespace, self.group, group)


class ICmdArgumentsSyntax(Interface):
    def arguments():
        """Defines the command line arguments syntax."""


class IContextualCmdArgumentsSyntax(Interface):
    def arguments(parser, args, rest):
        """Dynamically defines the command line arguments
        based on the partially parsed arguments and possibly
        and an unparsed trailing.

        It can return a deferred, if necessary.

        """
