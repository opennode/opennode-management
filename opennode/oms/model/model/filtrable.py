from grokcore.component import Adapter, context
from zope.interface import Interface, implements

from opennode.oms.model.schema import get_schema_fields
from opennode.oms.model.model.base import IModel


class IFiltrable(Interface):
    def match(query):
        """Returns true if this object matches the given query."""


class ModelFieldFiltrable(Adapter):
    implements(IFiltrable)
    context(IModel)

    def match(self, query):
        terms = [t for t in query.split(' ') if t]

        def matches(keyword, value):
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

        def any_field(keyword):
            return any(matches(keyword, field.get(schema(self.context)))
                       for name, field, schema in get_schema_fields(self.context))

        def specific_field(fieldname, value):
            schema = get_schema_fields(self.context)
            result = filter(lambda (name, field, schema): name == fieldname,
                            get_schema_fields(self.context))

            if len(result) == 0:
                return False

            name, field, schema = result[0]
            fieldvalue = field.get(schema(self.context))
            return matches(value, fieldvalue)

        return all(any_field(term.lower()) if ':' not in term else specific_field(*term.split(':')[0:2])
                   for term in terms)


class DefaultFiltrable(Adapter):
    implements(IFiltrable)
    context(object)

    def match(self, query):
        return False
