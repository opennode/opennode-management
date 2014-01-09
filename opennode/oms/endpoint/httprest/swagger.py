import json
from twisted.web import server
from twisted.web.resource import Resource


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
    def __init__(self, spec):
        Resource.__init__(self)
        self._spec = spec

    def render_GET(self, request):
        self.add_cors_headers(request)

        request.setHeader('Content-Type', 'application/json')

        return json.dumps(self._spec)


class SwaggerResource(JsonResource):
    def __init__(self):
        JsonResource.__init__(self, {
            "apiVersion": "0.1",
            "swaggerVersion": "1.2",
            "apis": [
                {
                    "path": "/etc",
                    "description": "Read-only access to configuration"
                }
            ]
        })

        etc = JsonResource({
            "apiVersion": "0.1",
            "swaggerVersion": "1.2",
            "basePath": "http://localhost:8080",
            "resourcePath": "/etc",
            "produces": ["application/json"],
            "models": {},
            "apis": [
                {
                    "path": "/etc",
                    "description": "Configuration section list",
                    "operations": [
                        {
                            "method": "GET",
                            "summary": "List all configuration sections",
                            "notes": "",
                            "responseClass": "EtcConfig",
                            "nickname": "getSections",
                            "parameters": [
                                {
                                    "paramType": "query",
                                    "name": "depth",
                                    "dataType": "integer",
                                    "defaultValue": 1,
                                    "required": False
                                }
                            ],
                            "errorResponses": [
                                {
                                    "code": 404,
                                    "message": "Configuration not found"
                                }
                            ]
                        }
                    ]
                },
                {
                    "path": "/etc/{name}",
                    "description": "Configuration section retrieval",
                    "operations": [
                        {
                            "method": "GET",
                            "nickname": "getSectionByName",
                            "responseClass": "EtcConfigSection",
                            "parameters": [
                                {
                                    "paramType": "path",
                                    "name": "name",
                                    "dataType": "string",
                                    "required": True
                                }
                            ],
                            "summary": "Find pet by its unique ID",
                            "notes": "Only Pets which you have permission to see will be returned",
                            "errorResponses": []
                        }
                    ]
                }
            ],
        })

        self.putChild('etc', etc)
