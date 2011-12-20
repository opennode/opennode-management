import argparse
import commands
import sys
import os
import opennode

from pyutils import autoreload
from twisted.scripts import twistd
from twisted.runner.procmon import ProcessMonitor


def run():
    """Starts the child zeo process and then starts the twisted reactor."""

    # HACK:autoreload will rerun this executable
    # we have to avoid reparsing the omsd commandlines
    # since we patched sys.argv for hooking into twistd.run
    args = None
    if sys.argv[1:] != ['-ny', 'opennode/oms.tac']:
        parser = argparse.ArgumentParser(description='Start OMS')
        parser.add_argument('-d', action='store_true',
                            help='start in development mode with autorestart')

        args = parser.parse_args()


    def get_base_dir():
        for i in opennode.__path__:
            base_dir = os.path.dirname(i)
            if os.path.exists(os.path.join(base_dir, 'opennode/oms.tac')):
                return base_dir
        raise Exception("cannot find base_dir")

    basedir = get_base_dir()
    os.chdir(basedir)

    db = 'db'

    # useful during development
    if os.path.exists('current_db_dir.sh'):
        db = commands.getoutput('./current_db_dir.sh')

    pm = ProcessMonitor()
    pm.addProcess('zeo', ['/bin/sh', '-c', 'runzeo -f %s/data.fs -a %s/socket >%s/zeo.log 2>&1' % (db, db, db)], env=os.environ)
    pm.startService()

    sys.argv=[sys.argv[0], '-ny', 'opennode/oms.tac']

    if args and args.d:
        autoreload.main(twistd.run)
    else:
        twistd.run()
