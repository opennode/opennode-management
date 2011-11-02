import shlex


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

    def tokenize(self, args):
        try:
            return self._handle_keywords(shlex.split(args, comments=True))
        except ValueError as e:
            raise CommandLineSyntaxError(str(e))

    def _handle_keywords(self, args):
        res = []
        for arg in args:
            if '=' in arg:
                keyword, value = arg.split('=', 1)
                res.append('=' + keyword)
                res.append(value)
            else:
                res.append(arg)

        return res
