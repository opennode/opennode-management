import zope.schema


__all__ = ['apply_raw_data']


def apply_raw_data(raw_data, schema, obj):
    """Takes a dict containing raw data as key-value pairs, converts
    the data to appropriate Python data types according to the schema,
    and validates the result.

    The passed in object `obj` is only modified if there are no
    datatype conversion nor validation errors.

    """

    tmp_obj = TmpObj(obj)

    errors = []
    for name, field in zope.schema.getFields(schema).items():
        if name not in raw_data:
            continue

        raw_value = raw_data.pop(name)

        if isinstance(raw_value, str):
            raw_value = raw_value.decode('utf8')

        try:
            value = field.fromUnicode(raw_value)
        except zope.schema.ValidationError as exc:
            errors.append((name, exc))
        else:
            setattr(tmp_obj, name, value)

    if raw_data:
        for key in raw_data:
            errors.append((key, 'Unknown attribute'))

    if not errors:
        errors = zope.schema.getValidationErrors(schema, tmp_obj)

    if not errors:
        tmp_obj.apply()

    return errors


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
            return getattr(self.__dict__['obj'], name)

    def __setattr__(self, name, value):
        self.__dict__['modified_attrs'][name] = value

    def apply(self):
        for name, value in self.__dict__['modified_attrs'].items():
            setattr(self.__dict__['obj'], name, value)
