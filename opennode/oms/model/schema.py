from collections import OrderedDict

from grokcore.component import context, Adapter, baseclass
from zope.component import getSiteManager, implementedBy
from zope.interface import implements
from zope.schema import TextLine, List, Set, getFieldsInOrder
from zope.schema.interfaces import IFromUnicode

from opennode.oms.util import get_direct_interfaces


class Path(TextLine):
    def __init__(self, *args, **kw):
        self.base_path = kw.pop('base_path', '')
        super(TextLine, self).__init__(*args, **kw)


def get_schemas(model_or_obj):
    for schema in get_direct_interfaces(model_or_obj):
        yield schema

    model = model_or_obj if isinstance(model_or_obj, type) else type(model_or_obj)

    for schema in getSiteManager().adapters._adapters[1].get(implementedBy(model), []):
        yield schema


def get_schema_fields(model_or_obj):
    for schema in get_schemas(model_or_obj):
        for name, field in getFieldsInOrder(schema):
            yield name, field, schema


class CollectionFromUnicode(Adapter):
    implements(IFromUnicode)
    baseclass()

    def fromUnicode(self, value):
        if isinstance(value, basestring):
            value = value.split(',')
        return self.context._type(value)


class ListFromUnicode(CollectionFromUnicode):
    context(List)


class SetFromUnicode(CollectionFromUnicode):
    context(Set)


# XXX: Might not be the best place nor name for it, but at least the
# duplication has been eliminated for now.
def model_to_dict(obj, use_titles=False):
    data = OrderedDict()
    for key, field, schema in get_schema_fields(obj):
        if not use_titles:
            key = key.encode('utf8')
        else:
            key = field.title
        data[key] = field.get(schema(obj))
    return data
