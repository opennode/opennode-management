from grokcore.component import Adapter, context
from zope.interface import Interface, implements

from opennode.oms.model.model.virtualizationcontainer import IVirtualizationContainer


backends = {'test': 'test:///tmp/func_vm_test_state.xml',
            'openvz': 'openvz:///system',
            'kvm': 'qemu:///system',
            'xen': 'xen:///'}


class IVirtualizationContainerSubmitter(Interface):
    def submit(job_interface):
        """Submits a job to the virtualization container"""


class FuncVirtualizationContainerSubmitter(Adapter):
    implements(IVirtualizationContainerSubmitter)
    context(IVirtualizationContainer)

    def submit(self, job_interface, *args):
        job = job_interface(self.context.__parent__)
        backend_uri = backends.get(self.context.backend, self.context.backend)
        return job.run(backend_uri, *args)
