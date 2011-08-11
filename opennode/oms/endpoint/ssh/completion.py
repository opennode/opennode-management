from columnize import columnize
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
    Currently completes only a when there is an unique match.
    """

    line = ''.join(buf)
    lead, rest = line[0:pos], line[pos:]

    tokens = lead.lstrip().split(' ')

    partial = tokens[-1]  # word to be completed

    if len(tokens) > 1:
        # TODO: Instantiating the cmd just for adaption is smelly.
        context = cmd.commands()[tokens[0]](protocol)
    else:
        context = None

    completers = querySubscriptions(context, ICompleter)
    completions = []
    for completer in completers:
        completions.extend(completer.complete(partial))

    if len(completions) == 1:
        space = '' if rest else ' '
        return completions[0][len(partial):] + space
    elif len(completions) > 1:
        # TODO: move screen fiddling back to protocol.py
        # this func should only contain high-level logic

        protocol.terminal.nextLine()
        protocol.terminal.write(columnize(completions))
        protocol.terminal.write(protocol.ps[protocol.pn])
        protocol.terminal.write(line)
        protocol.terminal.cursorBackward(len(rest))
