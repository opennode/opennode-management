from __future__ import absolute_import

from .base import ReadonlyContainer
from .compute import Computes
from .machines import Machines
from .proc import Proc
from .template import Templates
from .bin import Bin
from .log import Log


class OmsRoot(ReadonlyContainer):
    """The root of the OMS DB.

    This model is the root of the object hierarchy.

    Absolute object traversals start from this object.

    """

    __name__ = ''

    _items = property(lambda self: {
        'computes': self.computes,
        'templates': self.templates,
        'machines': self.machines,
        'bin': self.bin,
        'proc': self.proc,
        'log': self.log
    })

    def __init__(self):
        self.computes = Computes()
        self.computes.__parent__ = self
        self.computes.__name__ = 'computes'

        self.templates = Templates()
        self.templates.__parent__ = self
        self.templates.__name__ = 'templates'

        self.machines = Machines()
        self.machines.__parent__ = self
        self.machines.__name__ = 'machines'

    @property
    def bin(self):
        bin = Bin()
        bin.__parent__ = self
        return bin

    @property
    def proc(self):
        proc = Proc()
        proc.__parent__ = self
        return proc

    @property
    def log(self):
        if not getattr(self, '_log', None):
            self._log = Log()
            self._log.__parent__ = self
        return self._log

    def __str__(self):
        return 'OMS root'
