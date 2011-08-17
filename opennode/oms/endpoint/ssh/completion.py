from grokcore.component import Subscription, implements, baseclass, querySubscriptions
from zope.interface import Interface


class ICompleter(Interface):
    def complete(token, parsed_args):
        """Takes a token and returns a list of possible completions
        according to the context given by the parsed (partial) command arguments object
        and possibly other state contained in the adapted object (usually a Cmd).
        """


class Completer(Subscription):
    implements(ICompleter)
    baseclass()


def complete(protocol, buf, pos):
    """Bash like dummy completion, not great like zsh completion.
    Problems: completion in the middle of a word will screw it (like bash)
    """

    line = ''.join(buf)
    lead, rest = line[0:pos], line[pos:]

    tokens = lead.lstrip().split(' ')

    partial = tokens[-1]  # word to be completed

    context, tokenized_args = protocol.parse_line(lead.rstrip(partial).lstrip())

    parser = context.arg_parser(partial=True)
    parsed_args = parser.parse_args(tokenized_args)

    # TODO: This isn't enough. We need a relaxed tokenizer.
    # Ignore leading quote when searching for completions.
    if partial.startswith('"'):
       partial = partial[1:]

    completers = querySubscriptions(context, ICompleter)
    completions = [completion
                   for completer in completers
                   for completion in completer.complete(partial, parsed_args)]

    return partial, rest, completions