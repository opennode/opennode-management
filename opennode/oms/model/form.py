import inspect

import zope.schema
from zope.component import handle
from zope.interface import Interface, implements
from zope.schema.interfaces import IFromUnicode, WrongType, RequiredMissing

from opennode.oms.util import get_direct_interfaces


__all__ = ['ApplyRawData']


class UnknownAttribute(zope.schema.ValidationError):
    """Unknown attribute"""


class NoSchemaFound(zope.schema.ValidationError):
    """No schema found for object"""


class IModelModifiedEvent(Interface):
    """Model was modified"""


class ModelModifiedEvent(object):
    implements(IModelModifiedEvent)

    def __init__(self, original, modified):
        self.original = original
        self.modified = modified


class ApplyRawData(object):

    def __init__(self, data, obj=None, model=None):
        assert isinstance(data, dict)
        assert (obj or model) and not (obj and model), "One of either obj or model needs to be provided, but not both"

        self.schemas = get_direct_interfaces(obj or model)

        self.data = data
        self.obj = obj
        self.model = model

    @property
    def errors(self):
        if hasattr(self, '_errors'):
            return self._errors

        self.tmp_obj = tmp_obj = TmpObj(self.obj)
        schemas = self.schemas
        raw_data = dict(self.data)

        errors = []

        if not schemas:
            errors.append((None, NoSchemaFound()))
        else:
            for schema in schemas:
                for name, field in zope.schema.getFields(schema).items():
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
                        setattr(tmp_obj, name, value)

            if raw_data:
                for key in raw_data:
                    errors.append((key, UnknownAttribute()))

            if not errors:
                errors = zope.schema.getValidationErrors(schema, tmp_obj)


        self._errors = errors
        return errors

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
            ret[key or '__all__'] = msg
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
        if getattr(self, name) != value:
            self.__dict__['modified_attrs'][name] = value

    def apply(self):
        original_attrs = {}
        for name, value in self.__dict__['modified_attrs'].items():
            original_attrs[name] = getattr(self.__dict__['obj'], name, None)
            setattr(self.__dict__['obj'], name, value)

        if self.__dict__['modified_attrs']:
            handle(self.__dict__['obj'], ModelModifiedEvent(original_attrs, self.__dict__['modified_attrs']))
