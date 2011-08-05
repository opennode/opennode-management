from __future__ import absolute_import
from zope.interface import classImplements

from grokcore.component import Adapter, context, baseclass
from twisted.internet import reactor
from func.overlord.client import Overlord
from func import jobthing

from opennode.oms.backend.operation import IFuncInstalled
from opennode.oms.backend.operation import IGetComputeInfo


class FuncBase(Adapter):
    """Base class for all Func method calls."""
    context(IFuncInstalled)
    baseclass() # to avoid grokking of this class 

    func_action = None

    def run(self):
        client = self._get_client()
        # we assume that all of the func actions are in the form of 'module.action'
        module_action, action_name = self.func_action.split('.')
        module = getattr(client, module_action)
        action = getattr(module, action_name)
        self.job_id = action()

        self.start_polling()

    def start_polling(self):
        return_code, results = self._get_client().job_status(self.job_id)
        if return_code in(jobthing.JOB_ID_FINISHED, jobthing.JOB_ID_REMOTE_ERROR):
            self._fire_events(results)
            return
        reactor.callLater(1, self.start_polling) 

    def _fire_events(self, data):
        # XXX: Sending signal to self.context
        pass

    def _get_client(self):
        """Return an instance of the Overlord."""
        return Overlord(self.context.hostname, async=True)

FUNC_ACTIONS = {IGetComputeInfo: 'hardware.info'}
FUNC_CLASSES = {}

# iterate over supported func functions creating a new class with a correct Func action
for interface, action in FUNC_ACTIONS.items():
    cls_name = 'Func%s' % interface.__name__[1:]
    FUNC_CLASSES[cls_name] = type(cls_name, (FuncBase, ), dict(func_action=action))
    globals()[cls_name] = FUNC_CLASSES[cls_name]
    classImplements(FUNC_CLASSES[cls_name], interface)

