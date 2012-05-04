from collections import OrderedDict

from grokcore.component import context, Adapter, baseclass
from zope.component import getSiteManager, implementedBy
from zope.interface import implements
from zope.schema import TextLine, List, Set, Tuple, Dict, getFieldsInOrder
from zope.schema.interfaces import IFromUnicode
from zope.security.proxy import removeSecurityProxy
from zope.security.interfaces import Unauthorized

from opennode.oms.util import get_direct_interfaces


class Path(TextLine):
    # the current directory of the command being executed
    CWD = 'cwd'
    # the parent of an object
    PARENT = 'parent'

    def __init__(self, *args, **kw):
        self.base_path = kw.pop('base_path', '')
        self.relative_to = kw.pop('relative_to', self.CWD)
        super(TextLine, self).__init__(*args, **kw)


def get_schemas(model_or_obj):
    model_or_obj = removeSecurityProxy(model_or_obj)

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
            value = [i.strip() for i in value.split(',')]
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
            return (IFromUnicode(self.context.key_type).fromUnicode(unicode(k)), IFromUnicode(self.context.value_type).fromUnicode(unicode(v)))

        return self.context._type([convert(k, v) for k, v in res.items()])


# XXX: Might not be the best place nor name for it, but at least the
# duplication has been eliminated for now.
def model_to_dict(obj, use_titles=False, use_fields=False):
    data = OrderedDict()
    got_unauthorized = False

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
            continue
    if got_unauthorized and not data:
        raise Unauthorized((obj, "any attribute", 'read'))
    return data
