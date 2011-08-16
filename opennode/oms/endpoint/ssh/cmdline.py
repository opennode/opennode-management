import sys, argparse

from grokcore.component import Subscription, implements, baseclass, querySubscriptions
from zope.interface import Interface

class ArgumentParsingError(Exception):

    def __init__(self, status, message=None):
        self.status = status
        self.message = message

    def __str__(self):
        return "ArgumentParsingError(%s)" % (self.message)

class ArgumentParsingInterrupted(ArgumentParsingError):

    def __init__(self):
        pass

    def __str__(self):
        return "ArgumentParsingInterrupted()"


class InstrumentableArgumentParser(argparse.ArgumentParser):
    """ArgumentParser subclass which returns an exception instead of exiting in case of errors,
    and allows all output to be redirected to a custom output stream."""

    def __init__(self, *args, **kwargs):
        self.file = kwargs.pop('file', None)
        super(InstrumentableArgumentParser, self).__init__(*args, **kwargs)

    def _print_message(self, message, file=None):
        if self.file != None: # not self.file doesn't play nicely with mocks
            file = self.file

        return super(InstrumentableArgumentParser, self)._print_message(message, file)

    def exit(self, status=0, message=None):
        raise ArgumentParsingInterrupted()

    def error(self, message):
        print >>self.file, message
        raise ArgumentParsingError(2, message)


class VirtualConsoleArgumentParser(InstrumentableArgumentParser):
    def __init__(self, *args, **kwargs):
        add_help = kwargs.pop('add_help', None)

        super(VirtualConsoleArgumentParser, self).__init__(add_help=False, *args, **kwargs)

        if add_help:
            self.add_argument('-h', '--help', action="store_true", help="show this help message and exit")


    def parse_args(self, args=None, namespace=None, partial=False):
        """If partial is true, it will attempt also to parse an incomplete commandline,
        useful during completion.
        """
        try:
            args = super(VirtualConsoleArgumentParser, self).parse_args(args, namespace)
            if args.help and not partial:
                self.print_help()
                raise ArgumentParsingInterrupted()
            return args
        except ArgumentParsingError as e:
            if partial:
                return super(VirtualConsoleArgumentParser, self).parse_args(args[:-2], namespace)
            raise e


class ICmdArgumentsSyntax(Interface):
    def arguments():
        """Defines the command line arguments syntax"""
