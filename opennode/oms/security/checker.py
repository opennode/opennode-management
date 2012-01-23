import inspect

from copy import copy
from zope.interface import implements
from zope.security._proxy import _Proxy as Proxy
from zope.security.checker import _available_by_default, getCheckerForInstancesOf, CheckerPublic, TracebackSupplement
from zope.security.interfaces import INameBasedChecker, Unauthorized, ForbiddenAttribute


class NoCheckerException(Exception):
    pass


def _select_checker(value, interaction):
    checker = getCheckerForInstancesOf(type(value))
    if not checker:
        # XXX: create an exception for that
        raise NoCheckerException('cannot build security proxy for %s' % value)
    # handle checkers for "primitive" types like str
    if type(checker) is object:
        return checker

    # create a custom instance
    bound_checker = copy(checker)
    bound_checker.interaction = interaction
    return bound_checker


def proxy_factory(value, interaction):
    try:
        return Proxy(value, _select_checker(value, interaction))
    except NoCheckerException:
        return value


class Checker(object):
    implements(INameBasedChecker)

    def __init__(self, get_permissions, set_permissions=None):
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
        if set_permissions is not None:
            assert isinstance(set_permissions, dict)
        self.set_permissions = set_permissions

        self.interaction = None

    def permission_id(self, name):
        'See INameBasedChecker'
        return self.get_permissions.get(name)

    def setattr_permission_id(self, name):
        'See INameBasedChecker'
        if self.set_permissions:
            return self.set_permissions.get(name)

    def check_getattr(self, object, name):
        'See IChecker'
        self.check(object, name)

    def check_setattr(self, object, name):
        'See IChecker'
        if self.set_permissions:
            permission = self.set_permissions.get(name)
        else:
            permission = None

        if permission is not None:
            if permission is CheckerPublic:
                return  # Public
            if self.interaction.checkPermission(permission, object):  # use local interaction
                return  # allowed
            else:
                __traceback_supplement__ = (TracebackSupplement, object)
                raise Unauthorized(object, name, permission)

        __traceback_supplement__ = (TracebackSupplement, object)
        raise ForbiddenAttribute(name, object)

    def check(self, object, name):
        'See IChecker'
        permission = self.get_permissions.get(name)
        if permission is not None:
            if permission is CheckerPublic:
                return  # Public
            if self.interaction.checkPermission(permission, object):  # use local interaction
                return
            else:
                __traceback_supplement__ = (TracebackSupplement, object)
                raise Unauthorized(object, name, permission)
        elif name in _available_by_default:
            return

        if name != '__iter__' or hasattr(object, name):
            __traceback_supplement__ = (TracebackSupplement, object)
            raise ForbiddenAttribute(name, object)

    def proxy(self, value):
        'See IChecker'
        if type(value) is Proxy:
            return value
        if inspect.ismethod(value):
            return value
        checker = getattr(value, '__Security_checker__', None)
        if checker is None:
            checker = _select_checker(value, self.interaction)  # pass interaction
            if checker is None:
                return value

        return Proxy(value, checker)
