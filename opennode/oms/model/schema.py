from collections import OrderedDict
import logging
import re
import sys

from grokcore.component import context, Adapter, baseclass
from zope.component import getSiteManager, implementedBy
from zope.interface import implements
from zope.schema import TextLine, List, Set, Tuple, Dict, getFieldsInOrder, Bool
from zope.schema.interfaces import IFromUnicode, InvalidDottedName
from zope.security.proxy import removeSecurityProxy
from zope.security.interfaces import Unauthorized

from opennode.oms.util import get_direct_interfaces


log = logging.getLogger(__name__)


_isdotted = re.compile(
    r"([a-zA-Z][a-zA-Z0-9_-]*)"
    r"([.][a-zA-Z][a-zA-Z0-9_-]*)*"
    # use the whole line
    r"$").match


class InvalidRestrictedHostname(InvalidDottedName):

    def __init__(self, *args, **kw):
        super(InvalidRestrictedHostname, self).__init__(*args, **kw)


class RestrictedHostname(TextLine):

    def __init__(self, *args, **kwargs):
        super(RestrictedHostname, self).__init__(*args, **kwargs)

    def _validate(self, value):
        super(TextLine, self)._validate(value)
        if not _isdotted(value):
            raise InvalidRestrictedHostname(value)


class Path(TextLine):
    # the current directory of the command being executed
    CWD = 'cwd'
    # the parent of an object
    PARENT = 'parent'

    def __init__(self, *args, **kw):
        self.base_path = kw.pop('base_path', '')
        self.relative_to = kw.pop('relative_to', self.CWD)
        super(TextLine, self).__init__(*args, **kw)


def model_implements_marker(model, marker):
    return (marker and isinstance(model, type) and hasattr(model, '__markers__')
            and marker in model.__markers__)


def get_schemas(model_or_obj, marker=None):
    model_or_obj = removeSecurityProxy(model_or_obj)

    for schema in get_direct_interfaces(model_or_obj):
        yield schema

    model = model_or_obj if isinstance(model_or_obj, type) else type(model_or_obj)

    for schema in getSiteManager().adapters._adapters[1].get(implementedBy(model), []):
        yield schema

    if model_implements_marker(model_or_obj, marker):
        yield marker


def get_schema_fields(model_or_obj, marker=None):
    for schema in get_schemas(model_or_obj):
        for name, field in getFieldsInOrder(schema):
            yield name, field, schema

    if model_implements_marker(model_or_obj, marker):
        for name, field in getFieldsInOrder(marker):
            yield name, field, marker


class CollectionFromUnicode(Adapter):
    implements(IFromUnicode)
    baseclass()

    def fromUnicode(self, value):
        if self.context.value_type:
            value_converter = IFromUnicode(self.context.value_type)
            from_unicode = lambda x: value_converter.fromUnicode(x)
        else:
            from_unicode = lambda x: x

        if isinstance(value, basestring):
            value = [from_unicode(unicode(i.strip())) for i in value.strip(', ').split(',')]
        return self.context._type(value)


class ListFromUnicode(CollectionFromUnicode):
    context(List)


class SetFromUnicode(CollectionFromUnicode):
    context(Set)


class TupleFromUnicode(CollectionFromUnicode):
    context(Tuple)


class DictFromUnicode(Adapter):
    implements(IFromUnicode)
    context(Dict)

    def fromUnicode(self, value):
        if isinstance(value, basestring):
            value = [i.split(':') for i in value.split(',')]
        res = self.context._type(value)

        def convert(k, v):
            return (IFromUnicode(self.context.key_type).fromUnicode(unicode(k)),
                    IFromUnicode(self.context.value_type).fromUnicode(unicode(v)))

        return self.context._type([convert(k, v) for k, v in res.items()])


class BoolFromUnicode(Adapter):
    implements(IFromUnicode)
    context(Bool)

    def fromUnicode(self, value):
        if type(value) is bool:
            return value

        return (value in ('True', 'true'))


def model_to_dict(obj, use_titles=False, use_fields=False):
    data = OrderedDict()
    got_unauthorized = False

    error_attributes = []
    for key, field, schema in get_schema_fields(obj):
        if use_fields:
            key = field
        elif not use_titles:
            key = key.encode('utf8')
        else:
            key = field.title
        try:
            data[key] = field.get(schema(obj))
        except Unauthorized:
            # skip field
            got_unauthorized = True
            error_attributes.append(key)
            log.warning('Object %s (attribute %s of %s): access unauthorized!', obj, key, schema(obj),
                        exc_info=sys.exc_info())
            continue

    data['mtime'] = obj.mtime
    data['ctime'] = obj.ctime

    if got_unauthorized and not data:
        raise Unauthorized((obj, error_attributes, 'read'))
    return data
