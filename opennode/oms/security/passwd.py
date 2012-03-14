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


def ask_password():
    pw = getpass("Password: ")
    confirm = getpass("Confirm password: ")
    if pw != confirm:
        print "Password mismatch, aborting"
        sys.exit(1)

    return hash_pw(pw)


def hash_pw(password):
    salt = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in xrange(4))
    h = hashlib.sha1(password)
    h.update(salt)
    return "{SSHA}" + encode(h.digest() + salt).rstrip()


def run():
    parser = argparse.ArgumentParser(description='Manage OMS passwords')
    parser.add_argument('user', help="user name")
    parser.add_argument('-g', help="group(s): comma separated list of groups the user belongs to", required=False, default=None)
    parser.add_argument('-s', action='store_true', help="force password prompt even if setting group(s) via -g", required=False, default=None)

    group = parser.add_mutually_exclusive_group()
    group.add_argument('-a', action='store_true', help="add user")
    group.add_argument('-d', action='store_true', help="delete user")
    group.add_argument('-c', action='store_true', help="check password, useful to troubleshoot login issues")

    args = parser.parse_args()

    conf = get_config()
    passwd_file = conf.get('auth', 'passwd_file')

    if not os.path.exists(passwd_file):
        with open(passwd_file, 'w') as f:
            pass

    if args.d:
        with open(passwd_file) as f:
            lines = f.readlines()
        with open(passwd_file, 'w') as f:
            for line in lines:
                if line.startswith(args.user + ':'):
                    continue
                print >>f, line,
    elif args.a:
        # check if user exists
        with open(passwd_file) as f:
            for line in f:
                if line.startswith(args.user + ':'):
                    print "User %s already exists" % args.user
                    sys.exit(1)

        pw = ask_password()
        with open(passwd_file, 'a') as f:
            print >>f, '%s:%s:%s' % (args.user, pw, args.g or 'users')
    elif args.c:
        password_checker = FilePasswordDB(passwd_file, hash=ssha_hash)
        credentials = UsernamePassword(args.user, getpass("Password: "))
        try:
            blocking_yield(password_checker.requestAvatarId(credentials))
        except UnauthorizedLogin:
            print "Wrong credentials"
            sys.exit(1)

        print "ok"
    else:
        with open(passwd_file) as f:
            lines = f.readlines()

        found = False
        for line in lines:
            if line.startswith(args.user + ':'):
                found = True
        if not found:
            print "User %s doesn't exists" % args.user
            sys.exit(1)

        pw = None
        if args.s or not args.g:
            pw = ask_password()

        with open(passwd_file, 'w') as f:
            for line in lines:
                if line.startswith(args.user + ':'):
                    user, old_pw, groups = line.split(':')
                    if args.g:
                        groups = args.g
                    if pw == None:
                        pw = old_pw

                    print >>f, '%s:%s:%s' % (user, pw, groups),
                else:
                    print >>f, line,
