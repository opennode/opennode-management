from contextlib import closing
from cStringIO import StringIO
from grokcore.component import context, Adapter
from zope.interface import Interface, implements

from opennode.oms.model.model.base import IModel
from opennode.oms.model.schema import model_to_dict


class IEditable(Interface):
    def toEditableString():
        """Convert object to a string (possibly multiline) for editing"""

    def fromEditableString():
        """Modify the object from a string (possibly multiline)"""


class EditableModelAdapter(Adapter):
    implements(IEditable)
    context(IModel)

    def toEditableString(self):
        obj = self.context

        with closing(StringIO()) as s:
            data = [(key, value)
                    for key, value
                    in model_to_dict(obj).items()]

            for key, value in data:
                if isinstance(value, dict):
                    pretty_value = ', '.join(['%s:%s' % i for i in value.items()])
                elif hasattr(value, '__iter__'):
                    strings = [str(i) for i in value]
                    if not isinstance(value, tuple):
                        strings = sorted(strings)
                    pretty_value = ', '.join(strings)
                else:
                    pretty_value = value
                print >>s, "%s = %s" % (key.encode('utf8'), str(pretty_value).encode('utf8'))

            return s.getvalue()
