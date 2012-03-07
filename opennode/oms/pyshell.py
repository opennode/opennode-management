#!/usr/bin/env python
#from IPython.Shell import IPShellEmbed

from __future__ import absolute_import

import IPython
import transaction
import logging

from opennode.oms.core import setup_environ
from opennode.oms.zodb import db
from opennode.oms.model.location import ILocation
from opennode.oms.model.traversal import traverse_path
from opennode.oms.model.model import OmsRoot
try:
    from opennode.oms.model.model import Computes, Compute, Templates, Template
except:
    # ignore, the knot plugin is not installed
    pass

from opennode.oms.model.traversal import traverse_path, traverse1
from opennode.oms.endpoint.httprest.view import IHttpRestView


def run():
    logging.basicConfig()
    setup_environ()

    dbroot = db.get_root()
    oms_root = dbroot['oms_root']
    computes = oms_root['computes']
    templates = oms_root['templates']

    commit = transaction.commit
    abort = transaction.abort

    def traverse(path):
        res, _ = traverse_path(oms_root, path)
        if not res:
            return None
        return res[-1]

    IPython.embed()
