import grokcore.security
import martian
from zope.security.checker import defineChecker

from opennode.oms.security.checker import Checker
from opennode.oms.security.directives import permissions


class SecurityGrokker(martian.ClassGrokker):
    martian.component(object)
    martian.directive(permissions, name='permissions')

    def execute(self, factory, config, permissions, **kw):
        if not permissions:
            return False

        # mandatory, otherwise zope's default Checker impl will be used
        # which doesn't play well in async frameworks like twisted.
        defineChecker(factory, Checker({},{}))

        for name, permission in permissions.items():
            config.action(
                discriminator=('protectName', factory, name),
                callable=grokcore.security.util.protect_getattr,
                args=(factory, name, permission),
                )

        return True
