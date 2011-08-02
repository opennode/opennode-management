#!/usr/bin/env python
from IPython.Shell import IPShellEmbed
import transaction

from opennode.oms import discover_adapters
from opennode.oms.zodb import db
from opennode.oms.model.model import OmsRoot, Computes, Compute, Templates, Template
from opennode.oms.model.traversal import traverse_path, traverse1

discover_adapters()


dbroot = db.get_root()
oms_root = dbroot['oms_root']
computes = oms_root['computes']
templates = oms_root['templates']

commit = transaction.commit
abort = transaction.abort

IPShellEmbed()()
