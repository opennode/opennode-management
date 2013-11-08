import datetime

from grokcore.component import implements
from zope.security.proxy import removeSecurityProxy

from opennode.oms.endpoint.ssh.cmd.base import Cmd
from opennode.oms.endpoint.ssh.cmd.directives import command
from opennode.oms.endpoint.ssh.cmd.security import require_admins_only
from opennode.oms.endpoint.ssh.cmdline import ICmdArgumentsSyntax, VirtualConsoleArgumentParser
from opennode.oms.model.model.base import IIncomplete
from opennode.oms.zodb import db


class DBAdminCat(Cmd):
    """Represents the fact that there is no command yet."""
    implements(ICmdArgumentsSyntax)

    command('dbcat')

    def arguments(self):
        parser = VirtualConsoleArgumentParser()
        parser.add_argument('oids', nargs='+')
        parser.add_argument('--tid', nargs='?')
        return parser

    @require_admins_only
    @db.ro_transact
    def execute(self, args):
        for oid in args.oids:
            try:
                obj = db.load_object(oid, args.tid)
            except Exception:
                self.write("No such object: %s\n" % oid)
            else:
                self._do_dbcat(obj, None)

    def _get_data(self, obj):
        for key in dir(obj):
            if key in ('__doc__',
                       '__dict__',
                       '_p_oid',
                       '_p_changed',
                       '_p_estimated_size',
                       '_p_jar',
                       '_p_mtime',
                       '_p_serial',
                       '_p_state',
                       '__markers__',
                      ):
                continue

            attr = getattr(obj, key)

            if callable(attr):
                continue

            if not isinstance(attr, property):
                yield (key, attr)
            else:
                try:
                    yield (key, attr.__get__(obj))
                    continue
                except TypeError as e:
                    pass
                except AttributeError as e:
                    pass
                yield (key, 'Error: "%s"' % e)

    def _do_dbcat(self, obj, filename=None):
        data = list(self._get_data(obj))
        max_title_len = max(len(title) for title, _ in data)

        for title, value in data:
            if isinstance(value, dict):
                # security proxies don't mimic tuple() perfectly
                # thus cannot be passed to "%" directly
                pretty_value = ', '.join(['%s:%s' % tuple(i) for i in value.items()])
            elif hasattr(value, '__iter__'):
                strings = [str(i) for i in value]
                if not isinstance(value, tuple):
                    strings = sorted(strings)
                pretty_value = ', '.join(strings)
            elif title in ('mtime', 'ctime') and isinstance(value, float):
                pretty_value = datetime.datetime.fromtimestamp(value).isoformat()
            else:
                pretty_value = value

            self.write("%s\t%s\n" % ((title.encode('utf8') + ':').ljust(max_title_len),
                                     str(pretty_value).encode('utf8')))

        if IIncomplete.providedBy(obj):
            self.write("-----------------\n")
            self.write("This %s is incomplete.\n" % (type(removeSecurityProxy(obj)).__name__))
