from opennode.oms.db import db
from opennode.oms.model.compute import Compute

class ComputeBO(object):

    @db.transact
    def get_computes(self, tags):
        """Returns basic information about all computes."""
        result = db.get_store().find(Compute)
        return [{'name': c.hostname} for c in result]

    @db.transact
    def get_compute_all_basic(self):
        """Returns basic information about all computes."""

        result = db.get_store().execute('SELECT name FROM compute')
        return [{'name': row[0]} for row in result.listcontent()]

    @db.transact
    def get_compute_one_basic(self, compute_id):
        """Returns basic information about a single compute."""

        result = db.get_store().execute('SELECT name FROM compute WHERE id = "%s"' % compute_id)
        row = result.get_one()
        return {'name': row[0]} if row else None

    @db.transact
    def create_compute(self, data):
        """Creates a new Compute."""

        if 'is_valid':
            uri = 'http://www.neti.ee/'
            success, ret = True, uri
        else:
            validation_errors = {
                'some_field': 'Some validation message/code',
            }
            success, ret = False, validation_errors

        return success, ret
