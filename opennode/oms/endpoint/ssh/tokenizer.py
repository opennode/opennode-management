from lepl import String, Add, Regexp, Whitespace, Star, Optional, Literal, FullFirstMatchException, Eos
from lepl.matchers.error import Error as LeplError


class CommandLineSyntaxError(Exception):
    """The commandline has a syntax error and cannot be even tokenized correctly"""
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return "CommandLineSyntaxError(%s)" % self.message


class CommandLineTokenizer(object):
    """Tokenizer for the commandline, handling escaped space, quotes, escaped quotes
    and also special key=value syntax. It tries to provide user friendly error messages where possible.
    """
    def __init__(self):
        # give a nice error message in case of unclosed quotes
        string = (String() | (Regexp('".*') & Eos()) ^ "unclosed quote")

        escaped_space = Literal('\\ ') > (lambda _: " ")
        escaped_term = (escaped_space | Regexp('[a-zA-Z0-9/._-]+'))[1:]

        def prefix_equals(values):
            """argparse can recognize switches by prefix, let's move '=' in front
            of the token so that we can treat it like a cmdline switch"""
            if len(values) > 1:
                return values
            value = values[0]
            return '='+value[:-1] if value.endswith('=') else value

        # an argument can be a quoted string or term containing escaped spaces
        # it can have a trailing '=' symbol, that will be attached to arg
        # but it will treat the following text as a separated token
        arg = (Literal('=') ^ "spurious =") | (Add( (string | escaped_term) & Optional('=')) > prefix_equals)

        # an argument list is a whitespace separated list of args
        arg_list = ( arg & ~Whitespace()[0:] )[0:]

        self.parser = arg_list.get_parse()


    def tokenize(self, args):
        try:
            return self.parser(args)
        except FullFirstMatchException as e:
            raise CommandLineSyntaxError(str(e))
        except LeplError as e:
            raise CommandLineSyntaxError(str(e.msg))
