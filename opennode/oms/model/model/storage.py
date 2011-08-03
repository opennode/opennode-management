from __future__ import absolute_import

from .base import Model


class Storage(Model):
    def __init__(self, size, state):
        self.size = size  # 1.1 GiB
        self.state = state  # online | offline | backup | snapshot | resize | degraded
