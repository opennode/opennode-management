from zope.schema import TextLine


class Path(TextLine):
    def __init__(self, *args, **kw):
        self.base_path = kw.pop('base_path', '')
        super(TextLine, self).__init__(*args, **kw)
