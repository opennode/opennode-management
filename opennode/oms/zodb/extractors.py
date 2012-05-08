from grokcore.component import querySubscriptions
from zope.interface import Interface

from opennode.oms.zodb.proxy import get_peristent_context


class IContextExtractor(Interface):
    def get_context():
        """
        Return a dictionary of context information to be associated with persistent
        objects returned by methods of a given class decorated by @transact
        """

def context_from_method(fun, args, kwargs):
    """Currently works only for methods by assuming that the first
    argument is `self`. Unfortunately we cannot know the dynamic binding
    for the method because the @transact decorator is invoked at class
    definition time.

    If `self` is already a persistent object with a context attached, then that context
    is returned, otherwise it searches for matching IContextExtractor subscription adpaters.

    """

    that = args[0] if args else None

    context = get_peristent_context(that)

    if that:
        extractors = querySubscriptions(that, IContextExtractor)
        if extractors:
            for i in extractors:
               context.update(i.get_context())

    return context
