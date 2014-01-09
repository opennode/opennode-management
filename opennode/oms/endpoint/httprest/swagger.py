import json
from twisted.web import server
from twisted.web.resource import Resource, NoResource


class CorsResourceMixin:
    def add_cors_headers(self, request):
        # Allow all origins
        request.setHeader('Access-Control-Allow-Origin', '*')
        # request.setHeader('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS')
        request.setHeader('Access-Control-Allow-Methods', 'GET')
        # Allow all headers
        request.setHeader('Access-Control-Allow-Headers', request.getHeader('Access-Control-Request-Headers'))
        # request.setHeader('Access-Control-Max-Age', 2520)  # 42 hours

    def render_OPTIONS(self, request):
        self.add_cors_headers(request)
        request.finish()
        return server.NOT_DONE_YET


class JsonResource(Resource, CorsResourceMixin):
    def get_data(self):
        raise NotImplemented

    def render_GET(self, request):
        self.add_cors_headers(request)

        request.setHeader('Content-Type', 'application/json')

        return json.dumps(self.get_data())


class StaticJsonResource(JsonResource):
    def __init__(self, data):
        JsonResource.__init__(self)
        self._data = data

    def get_data(self):
        return self._data


class SwaggerResource(JsonResource):
    def __init__(self, base_path="http://localhost:8080"):
        Resource.__init__(self)
        self.base_path = base_path

    def getChild(self, path, request):
        containers = dict(self.get_containers())

        try:
            container = containers[path]
        except KeyError:
            return NoResource()

        item_name = self.get_container_item_name(container)

        # TODO: Handle Containers containing Containers, e.g. Computes/OpenVZContainer/IVirtualCompute
        # TODO: Make use of txswagger model
        # TODO: Extract get_* into txswagger SpecProvider
        # TODO: Handle AddingContainer
        # TODO: Handle ByNameContainer
        # TODO: Describe error responses
        # TODO: Handle OMS model to swagger model conversion
        apis = [
            {
                "path": "/%s" % path,
                # "description": "Configuration section list",
                "operations": [
                    {
                        "method": "GET",
                        "summary": "List %ss" % item_name,
                        "notes": "",
                        # "responseClass": "EtcConfig",
                        "nickname": "get%ss" % item_name,
                        "parameters": [
                            {
                                "paramType": "query",
                                "name": "depth",
                                "dataType": "integer",
                                "defaultValue": 1,
                                "required": False
                            }
                        ],
                        "errorResponses": []
                    }
                ]
            },
            {
                "path": "/%s/{name}" % path,
                # "description": "Configuration section retrieval",
                "operations": [
                    {
                        "method": "GET",
                        "nickname": "get%sByName" % item_name,
                        # "responseClass": "EtcConfigSection",
                        "parameters": [
                            {
                                "paramType": "path",
                                "name": "name",
                                "dataType": "string",
                                "required": True
                            }
                        ],
                        "summary": "Find %s by its unique name" % item_name,
                        "notes": "",
                        "errorResponses": []
                    }
                ]
            }
        ]

        return StaticJsonResource({
            "apiVersion": "0.1",
            "swaggerVersion": "1.2",
            "basePath": self.base_path,
            "resourcePath": "/%s" % path,
            "produces": ["application/json"],
            "models": {},  # TODO: Infer models
            "apis": apis
        })

    def get_data(self):
        apis = [
            {"path": "/%s" % name, "description": self.get_container_description(container)}
            for name, container in self.get_containers()
        ]

        return {
            "apiVersion": "0.1",
            "swaggerVersion": "1.2",
            "apis": apis
        }

    def get_container_description(self, container):
        try:
            return container.__doc__.strip().splitlines()[0].strip().strip('.')
        except (AttributeError, IndexError):
            return 'Not documented'

    def get_container_item_name(self, container):
        try:
            itemName = container.__contains__.__name__
        except AttributeError:
            # XXX: Hack for Plugins, its __contains__ attribute is missing
            itemName = 'UndocumentedItem'

        # XXX: Hack for some containers containing interfaces, others classes
        import re
        if re.match('^I[A-Z]', itemName):
            itemName = itemName[1:]

        return itemName

    def get_containers(self):
        from itertools import chain

        from grokcore.component.subscription import querySubscriptions
        from opennode.oms.model.model.base import IContainerInjector, IContainerExtender
        from opennode.oms.model.model.root import OmsRoot

        injectors = querySubscriptions(OmsRoot(), IContainerInjector)
        extenders = querySubscriptions(OmsRoot(), IContainerExtender)

        return chain(
            (
                (name, container)
                for injector in injectors
                for name, container in injector.inject().iteritems()
            ),
            (
                (name, container)
                for extender in extenders
                for name, container in extender.extend().iteritems()
            )
        )

