from .base import Model, Container


class Template(Model):
    def __init__(self, name, base_type, min_cores, max_cores, min_memory, max_memory):
        self.name = name
        self.base_type = base_type
        self.min_cores = min_cores
        self.max_cores = max_cores
        self.min_memory = min_memory
        self.max_memory = max_memory
        self.computes = []


class Templates(Container):
    __contains__ = Template

    def __str__(self):
        return 'Template list'
