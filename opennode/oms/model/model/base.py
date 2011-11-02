from uuid import uuid4

import persistent
from BTrees.OOBTree import OOBTree
from grokcore.component import querySubscriptions
from zope.interface import implements, directlyProvidedBy, Interface, Attribute
from zope.interface.interface import InterfaceClass
from opennode.oms.util import get_direct_interfaces


class IModel(Interface):
    __name__ = Attribute("Name")
    __parent__ = Attribute("Parent")

    def display_name():
        """Optionally returns a better display name instead of the __name__ when __name__ is more like an ID."""

    def implemented_interfaces():
        """Returns the interfaces implemented by this model."""


class IContainer(IModel):

    def __getitem__(key):
        """Returns the child item in this container with the given name."""

    def listnames():
        """Lists the names of all items contained in this container."""

    def listcontent():
        """Lists all the items contained in this container."""

    def __iter__():
        """Returns an iterator over the items in this container."""


class IIncomplete(Interface):
    def missing_parts():
        """Lists all the missing items which this object lacks before it can the
        incomplete marker can be removed.

        """


class Model(persistent.Persistent):
    implements(IModel)

    __parent__ = None
    __name__ = None

    def display_name(self):
        return None

    def implemented_interfaces(self):
        return get_direct_interfaces(type(self)) + list(directlyProvidedBy(self).interfaces())


class IContainerExtender(Interface):
    def extend(self):
        """Extend the container contents with new elements."""


class ReadonlyContainer(Model):
    """A container whose items cannot be modified, i.e. are predefined."""
    implements(IContainer)

    def __getitem__(self, key):
        return self.content().get(key)

    def listnames(self):
        return self.content().keys()

    def listcontent(self):
        return self.content().values()

    def __iter__(self):
        return iter(self.listcontent())

    def content(self):
        items = dict(**self._items)

        extenders = querySubscriptions(self, IContainerExtender)
        for extender in extenders:
            items.update(extender.extend())

        return items

    _items = {}


class AddingContainer(ReadonlyContainer):
    """A container which can accept items to be added to it.
    Doesn't actually store them, so it's up to subclasses to implement `_add`
    and override `listcontent` and `listnames`.

    """

    def can_contain(self, item):
        if isinstance(self.__contains__, InterfaceClass):
            return self.__contains__.providedBy(item) or self.__contains__.implementedBy(item)
        else:
            return isinstance(item, self.__contains__) or issubclass(item, self.__contains__)

    def _new_id(self):
        return str(uuid4())

    def add(self, item):
        if not self.can_contain(item):
            raise Exception("Container can only contain instances of or objects providing %s" % self.__contains__.__name__)

        return self._add(item)

    def rename(self, old_name, new_name):
        self._items[new_name] = self._items[old_name]
        del self._items[old_name]
        self._items[new_name].__name__ = new_name


class Container(AddingContainer):
    """A base class for containers whose items are named by their __name__.
    Adding unnamed objects will allocated using the overridable `_new_id` method.

    Does not support `__setitem__`; use `add(...)` instead.

    """

    __contains__ = Interface

    def __init__(self):
        self._items = OOBTree()

    def _add(self, item):
        if item.__parent__:
            if item.__parent__ is self:
                return
            item.__parent__.remove(item)
        item.__parent__ = self

        id = getattr(item, '__name__' , None)
        if not id:
            id = self._new_id()

        self._items[id] = item
        item.__name__ = id

        return id

    def remove(self, item):
        del self._items[item.__name__]

    def __delitem__(self, key):
        del self._items[key]
