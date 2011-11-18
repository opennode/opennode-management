import inspect

import zope.schema
from zope.component import handle
from zope.interface import Interface, implements
from zope.schema.interfaces import IFromUnicode, WrongType, RequiredMissing

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


class ModelDeletedEvent(object):
    implements(IModelDeletedEvent)

    def __init__(self, container):
        self.container = container


class ApplyRawData(object):

    def __init__(self, data, obj=None, model=None):
        assert isinstance(data, dict)
        assert (obj or model) and not (obj and model), "One of either obj or model needs to be provided, but not both"

        self.schemas = list(get_schemas(obj or model))
        self.fields = list(get_schema_fields(obj or model))

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
                    errors.extend(zope.schema.getValidationErrors(schema, self.adapted_tmp_obj(tmp_obj, schema)))

        self._errors = errors
        return errors

    def adapted_tmp_obj(self, tmp_obj, schema):
        adapter_cls = query_adapter_for_class(self.model or type(self.obj), schema)
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

    def __init__(self, wrapped):
        self.__dict__['obj'] = wrapped
        self.__dict__['modified_attrs'] = {}

    def __getattr__(self, name):
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

        if self.__dict__['modified_attrs']:
            handle(self.__dict__['obj'], ModelModifiedEvent(original_attrs, self.__dict__['modified_attrs']))
