import argparse
import os
import pkg_resources
import re
import subprocess
import sys
import urllib2

from BeautifulSoup import BeautifulSoup
from ConfigParser import ConfigParser, NoOptionError
from pkg_resources import working_set

__all__ = 'run'

ENTRY_POINT_NAME = 'oms.plugins'

def run():
    """bin/plugin allows to add/remove plugins to the eggnest"""

    parser = argparse.ArgumentParser(description='Start OMS')
    subparsers = parser.add_subparsers(title='subcommands',
                                       description='valid subcommands',
                                       help='additional help')

    install_parser = subparsers.add_parser('install', help='install a plugin')
    uninstall_parser = subparsers.add_parser('uninstall', help='uninstall a plugin')
    list_parser = subparsers.add_parser('list', help='list installed plugins')
    search_parser = subparsers.add_parser('search', help='search for available plugins')

    # opts

    install_parser.add_argument('plugin')
    install_parser.add_argument('-d', help="Path to plugin checkout")
    install_parser.add_argument('-n', action='store_true', help="Update to newest dependencies (might be slow)")
    install_parser.set_defaults(func=install_plugin)

    uninstall_parser.add_argument('plugin')
    uninstall_parser.set_defaults(func=uninstall_plugin)

    list_parser.set_defaults(func=list_plugins)

    search_parser.add_argument('plugin', nargs='?')
    search_parser.set_defaults(func=search_plugins)

    # common opts

    for i in (install_parser, uninstall_parser, search_parser):
        i.add_argument('--find-links')

    # run

    args = parser.parse_args()
    args.func(args)


def install_plugin(args):
    """Install an oms plugin and rerun `buildout` to update the omsd python path"""

    eggnest_file = os.path.join('eggnest', args.plugin) + '.cfg'
    with file(eggnest_file, 'w') as f:
        print >>f, '[eggnest]\negg = %s' % args.plugin
        if args.d:
            print >>f, 'develop = %s' % args.d

    newest = '-n' if args.n else '-N'
    sys.exit(subprocess.check_call('bin/buildout %s' % newest, shell=True))


def uninstall_plugin(args):
    """Uninstall an oms plugin and rerun `buildout` to update the omsd python path"""

    eggnest_file = os.path.join('eggnest', args.plugin) + '.cfg'
    if not os.path.exists(eggnest_file):
        print "Plugin '%s' is not installed" % args.plugin
        sys.exit(1)

    os.remove(eggnest_file)
    sys.exit(subprocess.check_call('bin/buildout -N', shell=True))


def list_plugins(args):
    """Lists installed oms plugins"""

    for i in _load_eggs(sys.path):
        dev = ''
        if not i.dist.location.endswith('.egg'):
            dev = ' [dev]'

        autodep = ''
        if not os.path.exists(os.path.join('eggnest', i.dist.key + '.cfg')):
            autodep = ' [autodep]'

        print "%s (%s)%s%s" % (i.dist.key, i.dist.version, dev, autodep)


def search_plugins(args):
    """Searches for eggs prefixed with `opennode.oms.` in the egg repository specified with `--find-links` or the default repo specified in the buildout conf."""

    if not args.plugin:
        args.plugin = ''

    url = args.find_links
    if not url:
        buildout = ConfigParser()
        buildout.read('buildout.cfg')
        url = buildout.get('buildout', 'find-links')

    plugins = {}

    soup = BeautifulSoup(urllib2.urlopen(url).read())
    for a in soup('a', {'href': re.compile('%s.*egg' % (args.plugin,))}):
        name, version = a['href'].split('-')[0:2]
        if name == 'opennode.oms.core' or not name.startswith('opennode.oms.'):
            continue

        if name in plugins:
            prev_version = plugins[name]
            if version > prev_version:
                plugins[name] = version
        else:
            plugins[name] = version

    for k, v in plugins.items():
        print "%s (%s)" % (k, v)


def _load_eggs(search_path, auto_enable=None):
    # Note that the following doesn't seem to support unicode search_path
    distributions, errors = working_set.find_plugins(
        pkg_resources.Environment(search_path)
    )
    for dist in distributions:
        if dist not in working_set:
            working_set.add(dist)

    def _log_error(item, e):
        print "[plugins] error loading", item, e

    for dist, e in errors.iteritems():
        # ignore version conflict of modules which are not OMS plugins
        if ENTRY_POINT_NAME in dist.get_entry_map():
            _log_error(dist, e)

    for entry in sorted(working_set.iter_entry_points(ENTRY_POINT_NAME),
                        key=lambda entry: entry.name):

        yield entry
