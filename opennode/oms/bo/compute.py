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

    @db.transact
    def create_compute(self, store, data):
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
