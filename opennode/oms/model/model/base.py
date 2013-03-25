from uuid import uuid4

import persistent
from BTrees.OOBTree import OOBTree
from grokcore.component import Subscription, querySubscriptions, baseclass
from zope import schema
from zope.annotation.interfaces import IAttributeAnnotatable
from zope.interface import implements, directlyProvidedBy, Interface, Attribute, alsoProvides, noLongerProvides
from zope.interface.interface import InterfaceClass
from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm
from zope.security.proxy import removeSecurityProxy
from zope.securitypolicy import interfaces

from opennode.oms.security.directives import permissions
from opennode.oms.util import get_direct_interfaces, exception_logger
from opennode.oms.model.form import ModelCreatedEvent, ModelMovedEvent, TmpObj
from zope.component import handle


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


class IDisplayName(Interface):
    def display_name():
        """Name for display"""


class IIncomplete(Interface):
    def missing_parts():
        """Lists all the missing items which this object lacks before it can the
        incomplete marker can be removed.

        """

class MarkerSourceBinder(object):
    implements(IContextSourceBinder)

    def __call__(self, context):
        names = [i.__name__ for i in getattr(context, '__markers__', None) or []]
        names = names + ['+' + i for i in names] + ['-' + i for i in names]

        # we need to include the current values even if they are not editable markers
        # otherwise the current object validation will fail (ON-403)
        # this is caused by the fact that the 'features' pseudo-field contains both
        # marker interfaces and real interfaces; this might change.
        # When it changes, we have to remove this union.
        current = (context.get_class_features() if isinstance(context, type) or isinstance(context, TmpObj)
                   else context.get_features())
        return SimpleVocabulary([SimpleTerm(i) for i in set(names).union(current)])


class IMarkable(Interface):
    """A model implementing this interfaces exposes marker interfaces
    via a 'features' pseudo attributes, and allows users to modify those attributes via set/mk.

    """
    features = schema.Set(title=u"Features", required=False,
                          value_type=schema.Choice(source=MarkerSourceBinder()))


class Model(persistent.Persistent):
    implements(IModel, IAttributeAnnotatable)
    permissions(dict(__name__='view'))

    __parent__ = None
    __name__ = None

    def set_owner(self, principal):
        prinrole = interfaces.IPrincipalRoleManager(self)
        prinrole.assignRoleToPrincipal('owner', principal.id)

    def get_owner(self):
        prinrole = interfaces.IPrincipalRoleManager(self)
        return map(lambda p: p[0],
                   filter(lambda p: p[1].getName() == 'Allow',
                          prinrole.getPrincipalsForRole('owner')))

    __owner__ = property(get_owner, set_owner)

    @classmethod
    def class_implemented_interfaces(cls):
        return get_direct_interfaces(cls)

    def implemented_interfaces(self):
        return self.class_implemented_interfaces() + list(directlyProvidedBy(self).interfaces())

    def _p_resolveConflict(self, oldState, savedState, newState):
        return newState

    @classmethod
    def get_class_features(cls):
        return set([i.__name__ for i in cls.class_implemented_interfaces()])

    def get_features(self):
        return set([i.__name__ for i in self.implemented_interfaces()])

    def set_features(self, values):
        """
        Features is a pseudo attribute which allows us to treat marker interfaces as if they were
        attributes. This special setter behaves like the tags setter, allowing addition and removal
        of individual marker interfaces from omsh.

        """
        # we have to reset the object otherwise indexing framework
        # won't update removed values
        features = set(self.get_features())

        def marker_by_name(name):
            for i in getattr(self, '__markers__', []):
                if i.__name__ == name:
                    return i
            return None

        if not any(i.startswith('-') or i.startswith('+') for i in values):
            for i in getattr(self, '__markers__', []):
                noLongerProvides(self, i)

        # ignore empty strings
        for value in (i for i in values if i):
            op = value[0] if value[0] in ['-', '+'] else None
            if op:
                value = value[1:]

            marker = marker_by_name(value)
            if marker:
                if op == '-':
                    if value in features:
                        noLongerProvides(self, marker)
                else:
                    alsoProvides(self, marker)

    features = property(get_features, set_features)


class IContainerExtender(Interface):
    def extend(self):
        """Extend the container contents with new elements."""


class IContainerInjector(Interface):
    def inject(self):
        """Injects models into the container. The injected models are persisted in the container."""


class ContainerExtension(Subscription):
    implements(IContainerExtender)
    baseclass()

    __class__ = None

    def extend(self):
        # XXX: currently models designed for container extension expect the parent
        # as constructor argument, but it's not needed anymore
        return {self.__class__.__dict__['__name__']: self.__class__(self.context)}


class ContainerInjector(Subscription):
    implements(IContainerInjector)
    baseclass()

    __class__ = None

    def inject(self):
        if '__name__' not in self.__class__.__dict__:
            raise KeyError('__name__ not found in __dict__ of (%s)' % (self.__class__))
        return {self.__class__.__dict__['__name__']: self.__class__()}


class ReadonlyContainer(Model):
    """A container whose items cannot be modified, i.e. are predefined."""
    implements(IContainer)
    permissions(dict(listnames='traverse',
                     listcontent='traverse',
                     __iter__='traverse',
                     __getitem__='traverse',
                     __contains__='read',
                     can_contain='add',
                     content='traverse',
                     add='add',
                     ))

    def __getitem__(self, key):
        return self.content().get(key)

    def listnames(self):
        return self.content().keys()

    def listcontent(self):
        return self.content().values()

    def __iter__(self):
        return iter(self.listcontent())

    def can_contain(self, item):
        """A read only container cannot accept new children"""
        return False

    @exception_logger
    def content(self):
        injectors = querySubscriptions(self, IContainerInjector)
        for injector in injectors:
            for k, v in injector.inject().items():
                if k not in self._items:
                    v.__parent__ = self
                    self._items[k] = v

        items = dict(**self._items)

        extenders = querySubscriptions(self, IContainerExtender)
        for extender in extenders:
            children = extender.extend()
            for v in children.values():
                v.__parent__ = self
            items.update(children)

        return items

    _items = {}


class AddingContainer(ReadonlyContainer):
    """A container which can accept items to be added to it.
    Doesn't actually store them, so it's up to subclasses to implement `_add`
    and override `listcontent` and `listnames`.

    """

    def can_contain(self, item):
        from opennode.oms.model.model.symlink import Symlink

        if isinstance(self.__contains__, InterfaceClass):
            if isinstance(item, Symlink):
                item = item.target
            if isinstance(item, type) and hasattr(item, '__markers__'):
                for item in item.__markers__:
                    if self.__contains__ == item:
                        return True
            return self.__contains__.providedBy(item) or self.__contains__.implementedBy(item)
        else:
            return isinstance(item, self.__contains__) or issubclass(item, self.__contains__)

    def _new_id(self):
        return str(uuid4())

    def add(self, item):
        if not self.can_contain(item):
            raise Exception("Can only contain instances or providers of %s" % self.__contains__.__name__)

        old_parent = item.__parent__
        res = self._add(item)

        if old_parent is not None and old_parent is not self:
            handle(item, ModelMovedEvent(item.__parent__, self))
        else:
            handle(item, ModelCreatedEvent(self))
        return res

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
        item = removeSecurityProxy(item)
        if item.__parent__:
            if item.__parent__ is self:
                return
            item.__parent__.remove(item)
        item.__parent__ = self

        id = getattr(item, '__name__', None)
        if not id:
            id = self._new_id()

        self._items[id] = item
        item.__name__ = id

        return id

    def remove(self, item):
        del self._items[item.__name__]

    def __delitem__(self, key):
        del self._items[key]
