from __future__ import absolute_import

from BTrees.OOBTree import OOTreeSet, difference
from grokcore.component import context, subscribe, Adapter, baseclass
from twisted.python import log
from zope import schema
from zope.app.catalog.catalog import Catalog
from zope.app.intid import IntIds
from zope.app.intid.interfaces import IIntIds
from zope.catalog.keyword import KeywordIndex
from zope.catalog.text import TextIndex
from zope.component import provideAdapter, provideUtility, provideSubscriptionAdapter, queryAdapter
from zope.interface import Interface, implements
from zope.keyreference.interfaces import NotYet
from zope.keyreference.persistent import KeyReferenceToPersistent
from zope.security.proxy import removeSecurityProxy

from .actions import ActionsContainerExtension, Action, action
from .base import ReadonlyContainer, AddingContainer, Model, IDisplayName, IContainer, IModel, Container
from .symlink import Symlink, follow_symlinks
from opennode.oms.model.form import IModelModifiedEvent, IModelCreatedEvent, IModelDeletedEvent


class ITokenized(Interface):
    def tokens():
        """Returns all tokens relevant for a model as a single string"""


class ITokenizer(Interface):
    def tokens():
        """Returns all tokens relevant for a model as a list of tokens"""


class ITagged(Interface):
    tags = schema.Set(title=u"Tags", required=False)


class ModelTokenizer(Adapter):
    implements(ITokenized)
    context(Model)

    def tokens(self):
        """Hackish way to quickly take all important tokens"""
        tokens = []
        if IDisplayName.providedBy(self.context):
            tokens.extend(IDisplayName(self.context).display_name().split('_'))

        if queryAdapter(self.context, ITagged):
            for tag in ITagged(self.context).tags:
                # hack, zope catalog treats ':' specially
                tokens.append(tag.replace(':', '_'))
                namespace, name = tag.split(':')
                tokens.append(name)

        return ' '.join(tokens)


class ModelTags(Adapter):
    implements(ITagged)
    baseclass()

    # TODO: obtain these prefixes from the declarations in the single models.
    __reserved_prefixes__ = set(['type', 'arch', 'virt', 'state'])

    def auto_tags(self):
        return set([])

    def _get_tags(self):
        # we have to check for None value because of TmpObj
        if not hasattr(self.context, '_tags') or self.context._tags is None:
            self.context._tags = set()
        return self.context._tags

    def _set_tags(self, value):
        self.context._tags = value

    def get_tags(self):
        return (set(self._get_tags())
                .union(set(self.auto_tags()))
                .union(set([u"type:" + type(removeSecurityProxy(self.context)).__name__.lower()])))

    def set_tags(self, values):
        """If tag names begin with + or - this setter will add or remove tags
        from the tag set, otherwise the set will be replaced.

        Tags are composed of a 'prefix' and a 'name'. If not specified, the default prefix is 'label:'.
        The user cannot add/remove tags in the one of the 'reserved prefixes'.

        """
        # we have to reset the object otherwise indexing framework
        # won't update removed values
        tags = set(self._get_tags())

        if not any(i.startswith('-') or i.startswith('+') for i in values):
            tags = set()

        # ignore empty strings
        for value in (i for i in values if i):
            op = value[0] if value[0] in ['-', '+'] else None
            if op:
                value = value[1:]

            if ':' not in value:
                value = u'label:' + value

            prefix, name = [i.strip() for i in value.split(':')]
            value = prefix + ':' + name

            if prefix in self.__reserved_prefixes__:
                continue
            if not name or not prefix:
                continue

            if op == '-':
                if value in tags:
                    tags.remove(value)
            else:
                tags.add(value)

        self._set_tags(tags)

    tags = property(get_tags, set_tags)


class SearchContainer(ReadonlyContainer):
    __name__ = 'search'

    def __init__(self):
        self.clear()

    def clear(self):
        self.tag_container = SearchByTagContainer(self)
        self.catalog = Catalog()
        self.catalog['tags'] = KeywordIndex('tags', ITagged)
        self.catalog['name'] = TextIndex('display_name', IDisplayName, True)
        self.catalog['__all'] = TextIndex('tokens', ITokenized, True)

        self.ids = IntIds()

    def index_object(self, obj):
        real_obj = follow_symlinks(obj)
        try:
            self.catalog.index_doc(self.ids.register(real_obj), real_obj)
        except NotYet:
            log.msg("cannot index object %s because it's not yet committed" % obj, system='search')

    def _index_object(self, obj):
        real_obj = follow_symlinks(obj)
        self.catalog.index_doc(self.ids.register(real_obj), real_obj)

    def unindex_object(self, obj):
        try:
            self.catalog.unindex_doc(self.ids.register(obj))
        except NotYet:
            log.msg("cannot unindex object %s because it's not yet committed" % obj, system='search')

    def search(self, **kwargs):
        # HACK, we should be able to setup a persistent utility
        provideUtility(self.ids, IIntIds)
        return list(self.catalog.searchResults(**kwargs))

    def search_goog(self, query):
        # hack, zope catalog treats ':' specially
        return self.search(__all=query.replace(':', '_'))

    @property
    def _items(self):
        return {'by-tag': self.tag_container}


class SearchResult(ReadonlyContainer):
    def __init__(self, parent, query):
        self.__parent__ = parent
        self.__name__ = query
        self.query = query

    def search_goog(self, query):
        return self.__parent__.search_goog(query)

    @property
    def _items(self):
        res = {}
        for item in self.__parent__.search_goog(self.query):
            name = item.__name__
            if IDisplayName.providedBy(item):
                name = IDisplayName(item).display_name()

            def find_free_name(tentative_name, idx):
                next_name = '%s_%s' % (name, idx)
                if tentative_name in res:
                    return find_free_name(next_name, idx + 1)
                return tentative_name

            name = find_free_name(name, 0)
            res[name] = Symlink(name, item)
        return res


@subscribe(Model, IModelModifiedEvent)
@subscribe(Model, IModelCreatedEvent)
@subscribe(Model, IModelDeletedEvent)
def enqueue_for_indexing(model, event):
    from opennode.oms.backend.indexer import IndexerDaemonProcess

    if isinstance(model, Symlink):
        return

    IndexerDaemonProcess.enqueue(model, event)


class ClearIndexAction(Action):
    """Clear index"""
    context(SearchContainer)

    action('clear-index')

    def execute(self, cmd, args):

        # TODO: break this import cycle by moving this action somewhere else
        from opennode.oms.zodb import db

        @db.transact
        def doit():
            search = db.get_root()['oms_root']['search']
            search.clear()

        return doit()


class ReindexAction(Action):
    """Force reindex"""
    context(SearchContainer)

    action('reindex')

    def execute(self, cmd, args):

        # TODO: break this import cycle by moving this action somewhere else
        from opennode.oms.zodb import db

        @db.transact
        def doit():
            search = db.get_root()['oms_root']['search']
            search.clear()

            objs = set()

            def collect(container):
                for item in container.listcontent():
                    # HACK, handle non indexable stuff:
                    if IContainer.providedBy(item) and not isinstance(item, Container):
                        continue

                    if IModel.providedBy(item) and not isinstance(item, Symlink):
                        objs.add(item)

                    if IContainer.providedBy(item):
                        collect(item)

            collect(db.get_root()['oms_root'])

            for obj in objs:
                search.index_object(obj)

            cmd.write("reindexed %s objects\n" % (len(objs)))

        return doit()


class ITag(Interface):
    name = schema.TextLine(title=u"Name")


class Tag(ReadonlyContainer):
    implements(ITag)

    def __init__(self, name, searcher, parent, other_tags, tag_path):
        self.name = name
        self.__name__ = name.encode('utf-8')
        self.__parent__ = parent
        self.searcher = searcher
        self.other_tags = difference(other_tags, OOTreeSet([self.__name__]))
        self.tag_path = tag_path + [name]

    @property
    def _items(self):
        res = {'items': TagItems(self, self.searcher)}
        for i in self.other_tags:
            sub_tag = Tag(i, self.searcher, self, self.other_tags, self.tag_path)

            # only add it if it yields some results.
            if TagItems(sub_tag, self.searcher)._items:
                res[i] = sub_tag
        return res


class TagItems(ReadonlyContainer):
    __name__ = 'items'

    def __init__(self, parent, searcher):
        self.__parent__ = parent
        self.searcher = searcher

    @property
    def _items(self):
        res = {}
        for item in self.searcher.search(tags=self.__parent__.tag_path):
            name = item.__name__
            if IDisplayName.providedBy(item):
                name = IDisplayName(item).display_name()

            def find_free_name(tentative_name, idx):
                next_name = '%s_%s' % (name, idx)
                if tentative_name in res:
                    return find_free_name(next_name, idx + 1)
                return tentative_name

            name = find_free_name(name, 0)
            res[name] = Symlink(name, item)
        return res


class SearchByTagContainer(AddingContainer):
    __name__ = 'by-tag'
    __contains__ = ITag

    def __init__(self, parent):
        self.__parent__ = parent

    @property
    def tags(self):
        return list(self.__parent__.catalog['tags']._fwd_index.keys())

    @property
    def _items(self):
        res = {}
        tag_set = OOTreeSet(self.tags)
        for i in self.tags:
            res[i] = Tag(i, self.__parent__, self, tag_set, [])
        return res

    def _add(self, item):
        self.tags.add(item.__name__)
        return item.__name__


provideAdapter(KeyReferenceToPersistent, adapts=(Model,))
provideSubscriptionAdapter(ActionsContainerExtension, adapts=(SearchContainer, ))
