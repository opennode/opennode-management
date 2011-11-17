from __future__ import absolute_import

from BTrees.OOBTree import OOTreeSet, difference
from grokcore.component import context, subscribe
from zope import schema
from zope.app.catalog.catalog import Catalog
from zope.app.intid import IntIds
from zope.app.intid.interfaces import IIntIds
from zope.catalog.keyword import KeywordIndex
from zope.catalog.text import TextIndex
from zope.component import provideAdapter, provideUtility, provideSubscriptionAdapter
from zope.interface import Interface, implements
from zope.keyreference.persistent import KeyReferenceToPersistent

from .actions import ActionsContainerExtension, Action, action
from .base import ReadonlyContainer, AddingContainer, Model, IDisplayName, IContainer, IModel, Container
from .symlink import Symlink, follow_symlinks
from opennode.oms.model.form import IModelModifiedEvent, IModelCreatedEvent, IModelDeletedEvent
from opennode.oms.model.traversal import canonical_path, traverse_path
from twisted.internet import reactor
from zope.keyreference.interfaces import NotYet
from twisted.python import log


class ITagged(Interface):
    """Taggable model"""
    def tags():
        """tag list"""


class SearchContainer(ReadonlyContainer):
    __name__ = 'search'

    def __init__(self):
        self.clear()

    def clear(self):
        self.tag_container = SearchByTagContainer(self)
        self.catalog = Catalog()
        self.catalog['tags'] = KeywordIndex('tags', ITagged)
        self.catalog['name'] = TextIndex('display_name', IDisplayName, True)
        self.ids = IntIds()

    def index_object(self, obj):
        real_obj = follow_symlinks(obj)
        try:
            self.catalog.index_doc(self.ids.register(real_obj), real_obj)
        except NotYet:
            log.msg("cannot index object because not yet committed")

    def unindex_object(self, obj):
        try:
            self.catalog.unindex_doc(self.ids.register(obj))
        except NotYet:
            log.msg("cannot index object because not yet committed")

    def search(self, **kwargs):
        # HACK, we should be able to setup a persistent utility
        provideUtility(self.ids, IIntIds)
        return list(self.catalog.searchResults(**kwargs))

    @property
    def _items(self):
        return {'by-tag': self.tag_container}


@subscribe(Model, IModelModifiedEvent)
def reindex_modified_model(model, event):
    # break import cycle
    from opennode.oms.zodb import db

    search = db.get_root()['oms_root']['search']
    search.index_object(model)


@subscribe(Model, IModelCreatedEvent)
def reindex_created_model(model, event):
    # break import cycle
    from opennode.oms.zodb import db

    @db.transact
    def get_and_reindex(retry, path):
        # we have to retrieve and index the object within this transaction
        # otherwise intid mapping won't be correct.
        objs, unresolved_path = traverse_path(db.get_root()['oms_root'], path)
        if unresolved_path:
            if retry < 5:
                reactor.callLater(0.1 * retry, get_and_reindex, retry + 1, canonical_path(model))
            return

        search = db.get_root()['oms_root']['search']
        search.index_object(objs[-1])

    # we cannot use the object in this transaction since it's not yet committed,
    # we'll retry to index it later, once the transaction is committed
    reactor.callLater(0.1, get_and_reindex, 0, canonical_path(model))


@subscribe(Model, IModelDeletedEvent)
def unindex_deleted_model(model, event):
    if isinstance(model, Symlink):
        return

    from opennode.oms.zodb import db
    search = db.get_root()['oms_root']['search']
    search.unindex_object(model)


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
                if res.has_key(tentative_name):
                    return find_free_name(next_name, idx+1)
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
