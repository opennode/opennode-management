import argparse
import os
import opennode
import random
import subprocess
import string
import sys

from contextlib import closing

from opennode.oms.config import get_config_cmdline
from opennode.oms.core import IApplicationInitializedEvent
from opennode.utils import autoreload

from grokcore.component import subscribe
from twisted.scripts import twistd
from twisted.runner.procmon import ProcessMonitor
from twisted.internet import defer


def get_base_dir():
    """Locates the base directory containing  opennode/oms.tac"""
    for i in opennode.__path__:
        base_dir = os.path.dirname(i)
        if os.path.exists(os.path.join(base_dir, 'opennode/oms.tac')):
            return base_dir
    raise Exception("cannot find base_dir")


def run_zeo(db):
    """Spawns a zeo daemon and restart it if it crashes"""
    runzeo = 'bin/runzeo'
    # XXX: compat mode for buildout-less runs
    if not os.path.exists('bin/runzeo'):
        runzeo = 'runzeo'

    pm = ProcessMonitor()
    pm.addProcess('zeo', ['/bin/sh', '-c', '%s -f %s/data.fs -a %s/socket >%s/zeo.log 2>&1' % (runzeo, db, db, db)], env=os.environ)
    pm.startService()


@subscribe(IApplicationInitializedEvent)
def ensure_zeo_is_running(event):
    """We start zeo after the application has performed the basic initialization
    because we cannot import opennode.oms.zodb.db until all grokkers are run in the
    correct order.

    """

    from opennode.oms.zodb.db import get_db_dir

    db_dir = get_db_dir()

    from zc.lockfile import LockFile, LockError
    try:
        with closing(LockFile(os.path.join(db_dir, 'data.fs.lock'))):
            print "Starting ZEO server"
        run_zeo(db_dir)
    except LockError:
        print "ZEO is already running"


def run_app():
    """Runs the application using opennode/oms.tac"""
    config = twistd.ServerOptions()
    config.parseOptions(['-ny', '%s/opennode/oms.tac' % (get_base_dir(),)])
    twistd._SomeApplicationRunner(config).run()


def run_debugger(args):
    module_file = sys.modules[__name__].__file__
    if args.debug:
        print "Waiting for debugger connection. Please attach a debugger, e.g.:"
        print "winpdb --attach %s" % (module_file)

        import rpdb2
        rpdb2.start_embedded_debugger(args.debug)
    if args.winpdb:
        rid = random.randint(1, 100000)
        pw = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in xrange(8))
        with closing(open(os.path.expanduser('~/.rpdb2_settings/passwords/%s' % rid), 'w')) as f:
            f.write(pw)

        print "Spawning winpdb"
        subprocess.Popen(['winpdb', '--rid', str(rid), '--attach', module_file])
        print "Waiting for debugger connection"

        import rpdb2
        rpdb2.start_embedded_debugger(pw)


def run():
    """Starts the child zeo process and then starts the twisted reactor running OMS"""

    parser = argparse.ArgumentParser(description='Start OMS')
    parser.add_argument('-d', action='store_true',
                        help='start in development mode with autorestart')
    parser.add_argument('--db', help='overrides db directory')
    parser.add_argument('-v', action='store_true', help='verbose logs')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--debug', help='waits for remote pdb attach using supplied password')
    group.add_argument('--winpdb', action='store_true', help='spawns winpdb and automaticall attach')

    args = parser.parse_args()

    conf = get_config_cmdline()
    if args.db:
        if not conf.has_section('db'):
            conf.add_section('db')
        conf.set('db', 'path', args.db)

    defer.setDebugging(args.v)

    run_debugger(args)

    if args and args.d:
        autoreload.main(run_app)
    else:
        run_app()
