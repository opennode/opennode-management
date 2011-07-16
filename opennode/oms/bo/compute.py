from opennode.oms import db


class ComputeBO(object):

    @db.transact
    def get_compute_all_basic(self, store):
        """Returns basic information about all computes."""

        result = store.execute('SELECT name FROM compute')
        return [{'name': row[0]} for row in result.get_all()]


    @db.transact
    def get_compute_one_basic(self, store, compute_id):
        """Returns basic information about a single compute."""

        result = store.execute('SELECT name FROM compute WHERE id = "%s"' % compute_id)
        row = result.get_one()
        return {'name': row[0]} if row else None
