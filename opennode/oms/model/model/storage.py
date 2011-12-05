from __future__ import absolute_import

from .base import Model


class Storage(Model):
    def __init__(self, size, state):
        self.id = 1  # UID
	self.name = "Local storage"  # description
	self.path = '/storagemount/local'
	self.type = local  # local | shared
	self.size = size  # 1.1 GiB
	self.used_size = 0
        self.state = state  # online | offline | backup | snapshot | resize | degraded
