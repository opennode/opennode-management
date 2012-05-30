import inspect

import zope.schema
from zope.component import handle
from zope.interface import Interface, implements
from zope.schema.interfaces import IFromUnicode, WrongType, RequiredMissing
from zope.security.proxy import removeSecurityProxy

from opennode.oms.model.schema import get_schemas, get_schema_fields
from opennode.oms.util import query_adapter_for_class


__all__ = ['ApplyRawData']


class UnknownAttribute(zope.schema.ValidationError):
    """Unknown attribute"""


class NoSchemaFound(zope.schema.ValidationError):
    """No schema found for object"""


class IModelModifiedEvent(Interface):
    """Model was modified"""


class IModelCreatedEvent(Interface):
    """Model was created"""


class IModelMovedEvent(Interface):
    """Model was moved"""


class IModelDeletedEvent(Interface):
    """Model was deleted"""


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


class ApplyRawData(object):

    def __init__(self, data, obj=None, model=None, marker=None):
        assert isinstance(data, dict)
        assert (obj or model) and not (obj and model), \
               "One of either obj or model needs to be provided, but not both"

        self.schemas = list(get_schemas(obj or model, marker=marker))
        self.fields = list(get_schema_fields(obj or model, marker=marker))

        self.data = data
        self.obj = obj
        self.model = model

    @property
    def errors(self):
        if hasattr(self, '_errors'):
            return self._errors

        self.tmp_obj = tmp_obj = TmpObj(self.obj)
        raw_data = dict(self.data)

        errors = []
        if not self.fields:
            errors.append((None, NoSchemaFound()))
        else:
            for name, field, schema in self.fields:
                if name not in raw_data:
                    continue

                field = field.bind(self.obj or self.model)

                raw_value = raw_data.pop(name)

                if isinstance(raw_value, str):
                    raw_value = raw_value.decode('utf8')

                # We don't want to accidentally swallow any adaption TypeErrors from here:
                from_unicode = IFromUnicode(field)

                try:
                    if not raw_value and field.required:
                        raise RequiredMissing(name)
                    try:
                        value = from_unicode.fromUnicode(raw_value)
                    except (ValueError, TypeError):
                        raise WrongType(name)
                except zope.schema.ValidationError as exc:
                    errors.append((name, exc))
                else:
                    setattr(self.adapted_tmp_obj(tmp_obj, schema), name, value)

            if raw_data:
                for key in raw_data:
                    errors.append((key, UnknownAttribute()))

            if not errors:
                for schema in self.schemas:
                    # XXX: We should not be adapting TmpObj's...  I've
                    # fixed the issue for no with the `if` but nobody
                    # knows what other issues this might cause in the
                    # future, or what other (hidden) issues adapting
                    # TmpObj's will cause.
                    adapted = self.adapted_tmp_obj(tmp_obj, schema)
                    errors.extend(zope.schema.getValidationErrors(schema, adapted))

        self._errors = errors
        return errors

    def adapted_tmp_obj(self, tmp_obj, schema):
        adapter_cls = query_adapter_for_class(self.model or type(removeSecurityProxy(self.obj)), schema)
        return adapter_cls(tmp_obj) if adapter_cls else tmp_obj

    def create(self):
        assert self.model, "model needs to be provided to create new objects"
        assert not self.errors, "There should be no validation errors"
        if self.model.__init__ is object.__init__:
            argnames = []
        else:
            argnames = inspect.getargspec(self.model.__init__).args

        kwargs, rest = {}, {}
        for name, value in self.data.items():
            (kwargs if name in argnames else rest)[name] = getattr(self.tmp_obj, name)

        obj = self.model(**kwargs)
        for name, value in rest.items():
            setattr(obj, name, value)

        return obj

    def apply(self):
        assert self.obj, "obj needs to be provided to apply changes to an existing object"
        assert not self.errors, "There should be no validation errors"
        self.tmp_obj.apply()

    def error_dict(self):
        ret = {}
        for key, error in self.errors:
            msg = error.doc().encode('utf8')
            ret[key if key is not None else '__all__'] = msg
        return ret

    def write_errors(self, to):
        for key, msg in self.error_dict().items():
            to.write("%s: %s\n" % (key, msg) if key is not '__all__' else "%s\n" % msg)


class TmpObj(object):
    """A proxy for storing and remembering temporary modifications to
    objects, and later applying them to the wrapped object.

    """

    __allowed_attrs__ = ['__markers__']

    def __init__(self, wrapped):
        self.__dict__['obj'] = wrapped
        self.__dict__['modified_attrs'] = {}

    def __getattr__(self, name):
        if name.startswith('__') and name not in TmpObj.__allowed_attrs__:
            raise AttributeError(name)
        if name in self.__dict__['modified_attrs']:
            return self.__dict__['modified_attrs'][name]
        else:
            obj = self.__dict__['obj']
            return getattr(obj, name) if obj else None

    def __setattr__(self, name, value):
        if getattr(self, name, object()) != value:
            self.__dict__['modified_attrs'][name] = value

    def apply(self):
        original_attrs = {}
        for name, value in self.__dict__['modified_attrs'].items():
            original_attrs[name] = getattr(self.__dict__['obj'], name, None)
            setattr(self.__dict__['obj'], name, value)

        # properties could alter the effective value of what we set
        # so we need to read back the actual values from the object
        updated = {}
        for k in self.__dict__['modified_attrs'].keys():
            new_value = getattr(self.__dict__['obj'], k)
            if new_value != original_attrs[k]:
                updated[k] = getattr(self.__dict__['obj'], k)
        # we emit modification events only for objects
        # that have been already added to a container (ON-412)
        if updated and self.__dict__['obj'].__parent__:
            handle(self.__dict__['obj'], ModelModifiedEvent(original_attrs, updated))


def alsoProvides(obj, interface):
    form = ApplyRawData({'features': '+' + interface.__name__}, obj)
    if not form.errors:
        form.apply()
    else:
        raise Exception("Cannot set marker interface %s" % interface)


def noLongerProvides(obj, interface):
    form = ApplyRawData({'features': '-' + interface.__name__}, obj)
    if not form.errors:
        form.apply()
    else:
        raise Exception("Cannot remove marker interface %s" % interface)
