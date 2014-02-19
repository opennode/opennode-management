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


# TODO: Handle Containers containing Containers, e.g. Computes/OpenVZContainer/IVirtualCompute
# TODO: Handle AddingContainer
# TODO: Handle ByNameContainer
# TODO: Make use of txswagger model
class BasicContainerDescriptor(object):
    def __init__(self, container, base_path):
        self.container = container
        self.base_path = base_path

    def get_apis(self):
        item_name = self.get_container_item_name()

        # For each api in container
        #  For each operation in container
        # TODO: Describe error responses
        apis = [
            {
                "path": "/%s" % self.base_path,
                "operations": [
                    {
                        "method": "GET",
                        "summary": "List %ss" % item_name,
                        "notes": "",
                        "type": "void",
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
                "path": "/%s/{name}" % self.base_path,
                "operations": [
                    {
                        "method": "GET",
                        "nickname": "get%sByName" % item_name,
                        "type": "void",  # TODO: Use corresponding model as type
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
        return apis

    def get_models(self):
        # TODO: Handle OMS model to swagger model conversion
        return {}

    def get_container_item_name(self):
        try:
            itemName = self.container.__contains__.__name__
        except AttributeError:
            # XXX: Hack for Plugins, its __contains__ attribute is missing
            itemName = 'UndocumentedItem'

        # XXX: Hack for some containers containing interfaces, others classes
        import re
        if re.match('^I[A-Z]', itemName):
            itemName = itemName[1:]

        return itemName


# TODO: Move to stoxy code base
class StoxyContainerDescriptor(BasicContainerDescriptor):
    def get_apis(self):
        # TODO: Describe error responses
        apis = [
            {
                "path": "/%s" % self.base_path,
                "operations": [
                    {
                        "method": "GET",
                        "summary": "List CDMI container contents",
                        "nickname": "getContents",
                        "type": "void",
                        "parameters": [
                            {
                                "paramType": "header",
                                "name": "x-cdmi-specification-version",
                                "dataType": "string",
                                "defaultValue": "1.0.2",
                                "required": False
                            },
                        ],
                        "errorResponses": []
                    },
                ]
            },
            {
                "path": "/%s/{entity}" % self.base_path,
                "operations": [
                    {
                        "method": "GET",
                        "summary": "GET CDMI container or object",
                        "nickname": "getEntity",
                        "type": "void",
                        "produces": ["application/cdmi-container", "application/cdmi-object"],
                        "parameters": [
                            {
                                "paramType": "path",
                                "name": "entity",
                                "dataType": "string",
                                "defaultValue": "",
                                "required": True
                            },
                            {
                                "paramType": "header",
                                "name": "x-cdmi-specification-version",
                                "dataType": "string",
                                "defaultValue": "1.0.2",
                                "required": False
                            },
                        ],
                        "errorResponses": []
                    },
                ]
            },
            {
                "path": "/%s/{container}" % self.base_path,
                "operations": [
                    {
                        "method": "PUT",
                        "summary": "Create CDMI container",
                        "nickname": "createContainer",
                        "type": "void",
                        "consumes": ["application/cdmi-container"],
                        "produces": ["application/cdmi-container"],
                        "parameters": [
                            {
                                "paramType": "path",
                                "name": "container",
                                "dataType": "string",
                                "defaultValue": "",
                                "required": True
                            },
                            {
                                "paramType": "body",
                                "name": "body",
                                "dataType": "CdmiEntity",
                                "defaultValue": "",
                                "required": True
                            },
                            {
                                "paramType": "header",
                                "name": "x-cdmi-specification-version",
                                "dataType": "string",
                                "defaultValue": "1.0.2",
                                "required": True
                            },
                        ],
                        "errorResponses": []
                    },
                ]
            },
            {
                "path": "/%s/{object}" % self.base_path,
                "operations": [
                    {
                        "method": "PUT",
                        "summary": "Create CDMI object",
                        "nickname": "createObject",
                        "type": "void",
                        "produces": ["application/cdmi-object"],
                        "consumes": ["application/cdmi-object"],
                        "parameters": [
                            {
                                "paramType": "path",
                                "name": "object",
                                "dataType": "string",
                                "defaultValue": "",
                                "required": True
                            },
                            {
                                "paramType": "body",
                                "name": "body",
                                "dataType": "CdmiEntity",
                                "defaultValue": "",
                                "required": True
                            },
                            {
                                "paramType": "header",
                                "name": "x-cdmi-specification-version",
                                "dataType": "string",
                                "defaultValue": "1.0.2",
                                "required": True
                            },
                        ],
                        "errorResponses": []
                    },
                ]
            },
            {
                "path": "/%s/{entity}" % self.base_path,
                "operations": [
                    {
                        "method": "DELETE",
                        "summary": "Delete CDMI container or object",
                        "nickname": "deleteEntity",
                        "type": "void",
                        "parameters": [
                            {
                                "paramType": "path",
                                "name": "entity",
                                "dataType": "string",
                                "defaultValue": "",
                                "required": True
                            },
                            {
                                "paramType": "header",
                                "name": "x-cdmi-specification-version",
                                "dataType": "string",
                                "defaultValue": "1.0.2",
                                "required": False
                            },
                        ],
                        "errorResponses": []
                    },
                ]
            },
        ]
        return apis

    def get_models(self):
        return {
            "CdmiEntity": {
                "id": "CdmiEntity",
                "required": [
                    "value",
                    "valuetransferencoding"
                ],
                "properties": {
                    "value": {
                        "type": "string"
                    },
                    "valuetransferencoding": {
                        "type": "string",
                        "description": "Transfer Encoding",
                        "enum": [
                            "utf-8",
                            "base64",
                        ]
                    },
                }
            }
        }

    def get_container_item_name(self):
        try:
            itemName = self.container.__contains__.__name__
        except AttributeError:
            # XXX: Hack for Plugins, its __contains__ attribute is missing
            itemName = 'UndocumentedItem'

        # XXX: Hack for some containers containing interfaces, others classes
        import re
        if re.match('^I[A-Z]', itemName):
            itemName = itemName[1:]

        return itemName


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

        # TODO: Infer descriptor class from container
        if path == 'storage':
            descriptor = StoxyContainerDescriptor(container, path)
        else:
            descriptor = BasicContainerDescriptor(container, path)

        return StaticJsonResource({
            "apiVersion": "0.1",
            "swaggerVersion": "1.2",
            "basePath": self.base_path,
            "resourcePath": "/%s" % path,
            "produces": ["application/json"],
            "models": descriptor.get_models(),
            "apis": descriptor.get_apis()
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

