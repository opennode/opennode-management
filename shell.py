#!/usr/bin/env python
#from IPython.Shell import IPShellEmbed
import IPython
import transaction
import logging

from opennode.oms import setup_environ
from opennode.oms.zodb import db
from opennode.oms.model.location import ILocation
from opennode.oms.model.model import OmsRoot, Computes, Compute, Templates, Template
from opennode.oms.model.traversal import traverse_path, traverse1
from opennode.oms.endpoint.httprest.view import IHttpRestView


logging.basicConfig()
setup_environ()


dbroot = db.get_root()
oms_root = dbroot['oms_root']
computes = oms_root['computes']
templates = oms_root['templates']

commit = transaction.commit
abort = transaction.abort

IPython.embed()
