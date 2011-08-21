import persistent
from BTrees.IOBTree import IOBTree
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


class Container(ReadonlyContainer):
    """A base class for containers whose items are identified by
    sequential integer IDs.

    Does not support `__setitem__`; use `add(...)` instead.

    """

    __contains__ = Interface

    def __init__(self):
        self._items = IOBTree()

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

        newid = self._items.maxKey() + 1 if self._items else 1
        self._items[newid] = item
        item.__name__ = str(newid)

    def remove(self, item):
        del self._items[item.__name__]

    def __delitem__(self, key):
        try:
            intkey = int(key)
        except ValueError:
            raise KeyError(key)
        else:
            del self._items[intkey]

    def __getitem__(self, key):
        """Returns the Template instance with the ID specified by the given key."""
        try:
            return self._items.get(int(key))
        except ValueError:
            return None
