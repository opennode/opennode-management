import martian
from grokcore.security import require
from grokcore.security.util import protect_getattr
from zope.security.checker import defineChecker

from opennode.oms.security.checker import Checker
from opennode.oms.endpoint.httprest.base import HttpRestView


class HttpRestViewSecurityGrokker(martian.ClassGrokker):
    """Specialized security permission directive which protects all render_* methods
    except render_OPTIONS.

    """
    martian.component(HttpRestView)
    martian.directive(require, name='permission')

    def execute(self, factory, config, permission, **kw):
        # mandatory, otherwise zope's default Checker impl will be used
        # which doesn't play well in async frameworks like twisted.
        defineChecker(factory, Checker({},{}))

        for method_name in [i for i in dir(factory) if i.startswith('render')]:
            config.action(
                discriminator=('protectName', factory, method_name),
                callable=protect_getattr,
                args=(factory, method_name, permission),
                )

        return True
