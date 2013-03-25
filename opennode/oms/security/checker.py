import inspect
import logging

from collections import defaultdict
from zope.interface import implements
from zope.security._definitions import thread_local
from zope.security._proxy import _Proxy as Proxy
from zope.security.checker import _available_by_default, getCheckerForInstancesOf
from zope.security.checker import CheckerPublic, TracebackSupplement, getChecker
from zope.security.interfaces import INameBasedChecker, Unauthorized, ForbiddenAttribute
from twisted.internet.defer import Deferred

from opennode.oms.config import get_config
from opennode.oms.security.principals import effective_principals


log = logging.getLogger(__name__)


_available_by_default.extend(['_p_oid', '__providedBy__', '__conform__'])


class strong_defaultdict(defaultdict):
    """Python's `defaultdict` type doesn't invoke default factory
    when called with `get`, we need this subclass to implement a permissive checker."""

    def get(self, name):
        return self[name]


def get_interaction(obj):
    """Extract interaction from a proxied object"""
    try:
        checker = getChecker(obj)
    except TypeError:
        return None

    if isinstance(checker, Checker):
        return checker.interaction
    else:
        return thread_local.interaction


class AuditingPermissionDictionary(dict):
    marker = object()

    seen = {}

    def __getitem__(self, key):
        return self.get(key)

    def get(self, key, default=None):
        val = super(AuditingPermissionDictionary, self).get(key, self.marker)
        if val is self.marker:
            if key not in _available_by_default:
                checker_locals = inspect.getouterframes(inspect.currentframe())[1][0].f_locals
                checker = checker_locals['self']
                principals = effective_principals(checker.interaction)
                seen_key = (key, ','.join(i.id for i in principals), type(checker_locals['obj']).__name__)
                if seen_key not in self.seen:
                    log.warning("Audit: permissive mode; granting attribute=%s, principals=(%s), obj=%s" %
                                seen_key)
                    self.seen[seen_key] = True
            return CheckerPublic
        return val


def _select_checker(value, interaction):
    checker = getCheckerForInstancesOf(type(value))
    if not checker:
        if get_config().getboolean('auth', 'enforce_attribute_rights_definition'):
            perms = {}
        else:
            if get_config().getboolean('auth', 'audit_all_missing_attribute_rights_definitions'):
                perms = AuditingPermissionDictionary()
            else:
                perms = strong_defaultdict(lambda: CheckerPublic)

        return Checker(perms, perms, interaction=interaction)

    # handle checkers for "primitive" types like str
    if type(checker) is object:
        return checker

    return Checker(checker.get_permissions, checker.set_permissions, interaction=interaction)


def proxy_factory(value, interaction):
    if type(value) is Proxy:
        return value
    # ignore proxies on deferreds
    if isinstance(value, Deferred):
        return value

    return Proxy(value, _select_checker(value, interaction))


class Checker(object):
    implements(INameBasedChecker)

    def __init__(self, get_permissions, set_permissions={}, interaction=None):
        """Create a checker

        A dictionary must be provided for computing permissions for
        names. The dictionary get will be called with attribute names
        and must return a permission id, None, or the special marker,
        CheckerPublic. If None is returned, then access to the name is
        forbidden. If CheckerPublic is returned, then access will be
        granted without checking a permission.

        An optional setattr dictionary may be provided for checking
        set attribute access.

        """
        assert isinstance(get_permissions, dict)
        self.get_permissions = get_permissions
        assert isinstance(set_permissions, dict)
        self.set_permissions = set_permissions

        self.interaction = interaction

    def permission_id(self, name):
        'See INameBasedChecker'
        return self.get_permissions.get(name)

    def setattr_permission_id(self, name):
        'See INameBasedChecker'
        return self.set_permissions.get(name)

    def check_getattr(self, obj, name):
        'See IChecker'
        self.check(obj, name)

    def _checkPermission(self, obj, name, permission):
        if permission is None:
            __traceback_supplement__ = (TracebackSupplement, obj)
            raise ForbiddenAttribute(name, obj)

        if permission is CheckerPublic:
            return

        # use local interaction
        if self.interaction.checkPermission(permission, obj):
            return

        __traceback_supplement__ = (TracebackSupplement, obj); __traceback_supplement__
        raise Unauthorized(obj, name, permission)

    def check_setattr(self, obj, name):
        'See IChecker'
        permission = self.set_permissions.get(name)
        self._checkPermission(obj, name, permission)

    def check(self, obj, name):
        'See IChecker'
        permission = self.get_permissions.get(name)
        if permission is None and name in _available_by_default:
            return
        self._checkPermission(obj, name, permission)

    def proxy(self, value):
        'See IChecker'
        if type(value) is Proxy:
            return value
        # ignore proxies on deferreds
        if isinstance(value, Deferred):
            return value
        # don't proxy classes
        if isinstance(value, type):
            return value
        checker = getattr(value, '__Security_checker__', None)
        if checker is None:
            checker = _select_checker(value, self.interaction)  # pass interaction
            if checker is None or type(checker) is object:
                return value

        return Proxy(value, checker)
