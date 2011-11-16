from __future__ import absolute_import

from grokcore.component import Subscription, baseclass
from zope.interface import implements

from .base import IContainerExtender, ReadonlyContainer, IDisplayName
from .symlink import Symlink, follow_symlinks


class ByNameContainer(ReadonlyContainer):
    """Implements a dynamic view creating a symlink for each parent's object
    which provides a `display_name()` value.

    """

    __name__ = 'by-name'

    def __init__(self, parent):
        self.__parent__ = parent

    def content(self):
        items = {}
        for item in self.__parent__.listcontent():
            real_item = follow_symlinks(item)

            # TODO: check why queryAdapter cannot be used here
            if IDisplayName.providedBy(real_item):
                named = IDisplayName(real_item)
                if named:
                    display_name = named.display_name()
                    items[display_name] = Symlink(display_name, item)

        return items


class ByNameContainerExtension(Subscription):
    implements(IContainerExtender)
    baseclass()

    def extend(self):
        return {'by-name': ByNameContainer(self.context)}

