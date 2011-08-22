from uuid import uuid4

import persistent
from BTrees.OOBTree import OOBTree
from zope.interface import implements, Interface, Attribute
from zope.interface.interface import InterfaceClass


class IModel(Interface):
    __name__ = Attribute("Name")
    __parent__ = Attribute("Parent")


class IContainer(IModel):

    def __getitem__(key):
        """Returns the child item in this container with the given name."""

    def listnames():
        """Lists the names of all items contained in this container."""

    def listcontent():
        """Lists all the items contained in this container."""


class Model(persistent.Persistent):
    implements(IModel)

    __parent__ = None
    __name__ = None


class ReadonlyContainer(Model):
    """A container whose items cannot be modified, i.e. are predefined."""
    implements(IContainer)

    def __getitem__(self, key):
        return self._items.get(key)

    def listnames(self):
        # Ensure the names are strings as _items might have integer keys.
        return (str(key) for key in self._items.keys())

    def listcontent(self):
        return self._items.values()


class SequentialIntegerIdPolicy(object):
    def new_id(self, container):
        return str(max(map(int, container._items)) + 1 if container._items else 1)


class UUIDIdPolicy(object):
    def new_id(self, container):
        return str(uuid4())


class Container(ReadonlyContainer):
    """A base class for containers whose items are named by their __name__.
    Adding unnamed objects will allocated according to the `id_allocation_policy`.

    Does not support `__setitem__`; use `add(...)` instead.

    """

    __contains__ = Interface

    id_allocation_policy = UUIDIdPolicy()

    def __init__(self):
        self._items = OOBTree()

    def can_contain(self, item):
        if isinstance(self.__contains__, InterfaceClass):
            return self.__contains__.providedBy(item) or self.__contains__.implementedBy(item)
        else:
            return isinstance(item, self.__contains__) or issubclass(item, self.__contains__)

    def add(self, item):
        if not self.can_contain(item):
            raise Exception("Container can only contain instances of or objects providing %s" % self.__contains__.__name__)

        if item.__parent__:
            if item.__parent__ is self:
                return
            item.__parent__.remove(item)
        item.__parent__ = self

        id = getattr(item, '__name__' , None)
        if not id:
            id = self.id_allocation_policy.new_id(self)

        self._items[id] = item
        item.__name__ = id

    def remove(self, item):
        del self._items[item.__name__]

    def __delitem__(self, key):
        del self._items[key]

    def __getitem__(self, key):
        """Returns the Template instance with the ID specified by the given key."""
        return self._items.get(key)
