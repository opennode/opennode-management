from zope.interface import Interface
from grokcore.component import Subscription, implements, baseclass, context, queryOrderedSubscriptions, querySubscriptions

from opennode.oms.endpoint.ssh import cmd

from columnize import columnize


def complete(protocol, buf, pos):
    """Bash like dummy completion, not great like zsh completion.
    Problems: completion in the middle of a word will screw it (like bash)
    Currently completes only a when there is an unique match.
    """

    line = ''.join(buf)
    lead, rest = line[0:pos], line[pos:]

    tokens = lead.lstrip().split(" ")

    partial = tokens[-1] # word to be completed

    context = None
    if len(tokens) > 1:
        context = cmd.commands()[tokens[0]](protocol)

    completers = querySubscriptions(context, ICompleter)
    candidates = []
    for completer in completers:
        candidates.extend(completer.complete(partial))

    if len(candidates) == 1:
        space = ""
        if not rest:
            space = " "
        return candidates[0][len(partial):] + space
    elif len(candidates) > 1:
        # TODO: move screen fiddling back to protocol.py
        # this func should only contain high-level logic

        protocol.terminal.nextLine()
        protocol.terminal.write(columnize(candidates))
        protocol.terminal.write(protocol.ps[protocol.pn])
        protocol.terminal.write(line)
        protocol.terminal.cursorBackward(len(rest))


class ICompleter(Interface):
    def complete(token):
        """Takes a token and returns a list of possible completions"""


class Completer(Subscription):
    implements(ICompleter)
    baseclass()

