import commands
import sys
import os
import opennode

from twisted.scripts import twistd
from twisted.runner.procmon import ProcessMonitor


def run():
    """Starts the child zeo process and then starts the twisted reactor."""

    basedir = os.path.dirname(os.path.dirname(opennode.__file__))
    os.chdir(basedir)

    db = 'db'

    # useful during development
    if os.path.exists('current_db_dir.sh'):
        db = commands.getoutput('./current_db_dir.sh')

    pm = ProcessMonitor()
    pm.addProcess('zeo', ['/bin/sh', '-c', 'runzeo -f %s/data.fs -a %s/socket >%s/zeo.log 2>&1' % (db, db, db)], env=os.environ)
    pm.startService()

    sys.argv=[sys.argv[0], '-ny', 'opennode/oms.tac']

    twistd.run()
