from zope.schema import TextLine, getFieldsInOrder

from opennode.oms.util import get_direct_interfaces


class Path(TextLine):
    def __init__(self, *args, **kw):
        self.base_path = kw.pop('base_path', '')
        super(TextLine, self).__init__(*args, **kw)


def get_schema_fields(model_or_obj):
    schemas = get_direct_interfaces(model_or_obj)
    for schema in schemas:
        for field in getFieldsInOrder(schema):
            yield field
