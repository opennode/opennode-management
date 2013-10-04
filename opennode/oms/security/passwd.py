import argparse
import hashlib
import os
import random
import string
import sys

from base64 import encodestring as encode
from getpass import getpass
from twisted.cred.checkers import FilePasswordDB
from twisted.cred.credentials import UsernamePassword
from twisted.cred.error import UnauthorizedLogin

from opennode.oms.config import get_config
from opennode.oms.security.authentication import ssha_hash
from opennode.oms.util import blocking_yield


class UserManagementError(Exception):
    def __init__(self, *args, **kw):
        super(UserManagementError, self).__init__(*args, **kw)


def ask_password():
    pw = getpass("Password: ")
    confirm = getpass("Confirm password: ")
    if pw != confirm:
        raise UserManagementError("Password mismatch, aborting")

    return pw


def get_salt():
    return ''.join(random.choice(string.ascii_uppercase + string.digits) for x in xrange(4))


def get_salt_dummy():
    return ''


def hash_pw(password, saltf=get_salt):
    salt = saltf()
    h = hashlib.sha1(password)
    h.update(salt)
    return "{SSHA}" + encode(h.digest() + salt).rstrip()


def ensure_base_dir():
    basedir = get_config().get_base_dir()
    if basedir:
        os.chdir(basedir)


def add_user(user, password, group=None, uid=None, force=False):
    restricted_users = get_config().getstring('auth', 'restricted_users', '').split(',')

    if user in map(string.strip, restricted_users) and not force:
        raise UserManagementError('User %s is restricted! Adding permission denied!' % user)

    passwd_file = get_config().getstring('auth', 'passwd_file')
    with open(passwd_file) as f:
        for line in f:
            if line.startswith(user + ':'):
                raise UserManagementError("User %s already exists" % user)

    with open(passwd_file, 'a') as f:
        f.write('%s:%s:%s:%s\n' % (user, hash_pw(password), group or 'users', uid))


def delete_user(user):
    passwd_file = get_config().get('auth', 'passwd_file')
    with open(passwd_file) as f:
        lines = f.readlines()

    with open(passwd_file, 'w') as f:
        for line in lines:
            if line.startswith(user + ':'):
                continue
            f.write(line)


def update_passwd(user, password=None, force_askpass=False, group=None, force=False):
    passwd_file = get_config().get('auth', 'passwd_file')
    restricted_users = get_config().getstring('auth', 'restricted_users', '').split(',')

    if user in map(string.strip, restricted_users) and not force:
        raise UserManagementError('User %s is restricted! Update permission denied!' % user)

    with open(passwd_file) as f:
        lines = f.readlines()

    found = False
    for line in lines:
        if line.startswith(user + ':'):
            found = True

    if not found:
        raise UserManagementError("User %s doesn't exist" % user)

    with open(passwd_file, 'w') as f:
        for line in lines:
            def parse_line(line):
                _user, pw, groups = line.split(':', 2)

                if ':' in groups:
                    groups, uid = groups.split(':', 1)
                else:
                    uid = None

                return _user, pw, groups, uid

            line = line.rstrip('\n')

            if line.startswith(user + ':'):
                pw = hash_pw(ask_password() if password is None
                             and (force_askpass or not group) else password)

                _user, old_pw, groups, uid = parse_line(line)

                if group:
                    groups = group

                if pw is None:
                    pw = old_pw

                f.write('%s:%s:%s:%s\n' % (_user, pw, groups, uid))
            else:
                _user, old_pw, groups, uid = parse_line(line)
                f.write('%s:%s:%s:%s\n' % (_user, old_pw, groups, uid))


def run():
    parser = argparse.ArgumentParser(description='Manage OMS passwords')
    parser.add_argument('user', help="user name")
    parser.add_argument('-g', help="group(s): comma separated list of "
                        "groups the user belongs to", required=False, default=None)
    parser.add_argument('-s', action='store_true', help="force password "
                        "prompt even if setting group(s) via -g",
                        required=False, default=None)

    group = parser.add_mutually_exclusive_group()
    group.add_argument('-a', action='store_true', help="add user")
    group.add_argument('-d', action='store_true', help="delete user")
    group.add_argument('-c', action='store_true', help="check password, useful "
                       "to troubleshoot login issues")

    args = parser.parse_args()

    ensure_base_dir()
    passwd_file = get_config().get('auth', 'passwd_file')

    if not os.path.exists(passwd_file):
        with open(passwd_file, 'w'):
            pass

    try:
        if args.d:
            delete_user(args.user)
        elif args.a:
            add_user(args.user, ask_password(), group=args.g)
        elif args.c:
            password_checker = FilePasswordDB(passwd_file, hash=ssha_hash)
            credentials = UsernamePassword(args.user, getpass("Password: "))
            try:
                blocking_yield(password_checker.requestAvatarId(credentials))
            except UnauthorizedLogin:
                raise UserManagementError("Wrong credentials")

            print "ok"
        else:
            update_passwd(args.user, args.s, force=True)
    except UserManagementError as e:
        print e
        sys.exit(1)
