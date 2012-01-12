from grokcore.component import Subscription, implements, baseclass, querySubscriptions
from twisted.internet import defer
from zope.interface import Interface


class ICompleter(Interface):
    def complete(token, parsed_args, parser, **kwargs):
        """Takes a token and returns a list of possible completions
        according to the context given by the parsed (partial) command arguments object
        and possibly other state contained in the adapted object (usually a Cmd).
        """


class Completer(Subscription):
    implements(ICompleter)
    baseclass()


@defer.inlineCallbacks
def complete(protocol, buf, pos, **kwargs):
    """Bash like dummy completion, not great like zsh completion.
    Problems: completion in the middle of a word will screw it (like bash)
    """

    line = ''.join(buf)
    lead, rest = line[0:pos], line[pos:]

    tokens = lead.lstrip().split(' ')

    partial = tokens[-1]  # word to be completed

    context, tokenized_args = yield protocol.parse_line(lead.rstrip(partial).lstrip())

    parser = yield context.contextual_arg_parser(tokenized_args, partial=True)
    parsed_args = yield parser.parse_args(tokenized_args)

    # TODO: This isn't enough. We need a relaxed tokenizer.
    # Ignore leading quote when searching for completions.
    if partial.startswith('"'):
        partial = partial[1:]

    completers = querySubscriptions(context, ICompleter)

    all_completions = []
    for completer in completers:
        completions = yield completer.complete(partial, parsed_args, parser, protocol=protocol, **kwargs)
        if completions:
            all_completions.extend(completions)

    defer.returnValue((partial, rest, all_completions))
