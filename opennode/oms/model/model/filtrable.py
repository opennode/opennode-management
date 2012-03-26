from grokcore.component import Adapter, context
from zope.interface import Interface, implements

from opennode.oms.model.schema import get_schema_fields
from opennode.oms.model.model.base import IModel


class IFiltrable(Interface):
    def match(query):
        """Returns true if this object matches the given query."""


class ModelFiltrable(Adapter):
    implements(IFiltrable)
    context(IModel)

    def match(self, query):
        keywords = [i.lower() for i in query.split(' ') if i]

        for name, field, schema in get_schema_fields(self.context):
            value = field.get(schema(self.context))

            for keyword in keywords:
                if isinstance(value, unicode):
                    value = value.encode('utf-8')

                if isinstance(value, str):
                    if keyword in value:
                        return True

                if isinstance(value, list) or isinstance(value, set):
                    if keyword in value:
                        return True

                if keyword == value:
                    return True

        return False


class DefaultFiltrable(Adapter):
    implements(IFiltrable)
    context(object)

    def match(self, query):
        return False
