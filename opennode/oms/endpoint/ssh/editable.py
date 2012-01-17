from contextlib import closing
from cStringIO import StringIO
from grokcore.component import context, Adapter
from zope.interface import Interface, implements

from opennode.oms.model.model.base import IModel
from opennode.oms.model.schema import model_to_dict


class IEditable(Interface):
    def toEditableString(descriptions=False):
        """Convert object to a string (possibly multiline) for editing"""

    def fromEditableString():
        """Modify the object from a string (possibly multiline)"""


class EditableModelAdapter(Adapter):
    implements(IEditable)
    context(IModel)

    def toEditableString(self, descriptions=False):
        obj = self.context

        with closing(StringIO()) as s:
            data = [(key, value, field)
                    for (key, value), field
                    in zip(model_to_dict(obj).items(), model_to_dict(obj, use_fields=True).keys())]

            for key, value, field in data:
                if isinstance(value, dict):
                    pretty_value = ', '.join(['%s:%s' % i for i in value.items()])
                elif hasattr(value, '__iter__'):
                    strings = [str(i) for i in value]
                    if not isinstance(value, tuple):
                        strings = sorted(strings)
                    pretty_value = ', '.join(strings)
                else:
                    pretty_value = value

                if field.readonly:
                    continue

                if descriptions and field.title:
                    print >>s, "##", field.title
                    if field.description:
                        print >>s, "#", field.description

                print >>s, "%s = %s" % (key.encode('utf8'), str(pretty_value).encode('utf8'))
                if descriptions:
                    print >>s, ''

            return s.getvalue()
