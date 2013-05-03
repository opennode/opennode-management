from zope.interface import Interface, implements


class IModelModifiedEvent(Interface):
    """Model was modified"""


class IModelCreatedEvent(Interface):
    """Model was created"""


class IModelMovedEvent(Interface):
    """Model was moved"""


class IModelDeletedEvent(Interface):
    """Model was deleted"""


class IOwnerChangedEvent(Interface):
    """Model owner has been changed"""



class ModelModifiedEvent(object):
    implements(IModelModifiedEvent)

    def __init__(self, original, modified):
        self.original = original
        self.modified = modified


class ModelCreatedEvent(object):
    implements(IModelCreatedEvent)

    def __init__(self, container):
        self.container = container


class ModelMovedEvent(object):
    implements(IModelMovedEvent)

    def __init__(self, fromContainer, toContainer):
        self.fromContainer = fromContainer
        self.toContainer = toContainer


class ModelDeletedEvent(object):
    implements(IModelDeletedEvent)

    def __init__(self, container):
        self.container = container


class OwnerChangedEvent(object):
    implements(IOwnerChangedEvent)

    def __init__(self, oldowner, newowner):
        self.oldowner = oldowner
        self.nextowner = newowner
