import zope.schema
from grokcore.component import Adapter, context
from zope.interface import Interface, implements

from opennode.oms.model.model.base import IModel
from opennode.oms.util import get_direct_interfaces


class IFiltrable(Interface):
    def match(query):
        """Returns true if this object matches the given query."""


class ModelFiltrable(Adapter):
    implements(IFiltrable)
    context(IModel)

    def match(self, query):
        keywords = [i.lower() for i in query.split(' ') if i]

        schemas = get_direct_interfaces(self.context)
        for schema in schemas:
            for name, field in zope.schema.getFields(schema).items():
                for keyword in keywords:
                    value = getattr(self.context, name, None)

                    if isinstance(value, unicode):
                        value = value.encode('utf-8')

                    if isinstance(value, str):
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
