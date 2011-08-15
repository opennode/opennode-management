from grokcore.component import Subscription, implements, baseclass, querySubscriptions
from zope.interface import Interface

from opennode.oms.endpoint.ssh import cmd


class ICompleter(Interface):
    def complete(token):
        """Takes a token and returns a list of possible completions"""


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

    # Ignore leading quote when searching for completions.
    # This isn't enough. We need a relaxed tokenizer.
    if partial.startswith('"'):
       partial = partial[1:]

    if len(tokens) > 1:
        # TODO: Instantiating the cmd just for adaption is smelly.
        # (but, it's not only for adaptation, some adapters need the cmd objects)
        context = cmd.commands()[tokens[0]](protocol)
    else:
        context = None

    completers = querySubscriptions(context, ICompleter)
    completions = [completion for completer in completers for completion in completer.complete(partial)]

    return (partial, rest, completions)
