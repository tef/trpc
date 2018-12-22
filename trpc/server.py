import types
import traceback
import sys
import os
import inspect

from urllib.parse import urljoin, urlencode, parse_qsl

from . import objects, client, cli, wsgi

def funcargs(m):
    signature = inspect.signature(m)
    args = signature.parameters
    args = [a for a in args if not a.startswith('_')]
    if args and args[0] == 'self': args.pop(0)
    return args

def rpc(expose=True):
    def _decorate(fn):
        fn.__rpc__ = expose
        return fn
    return _decorate

class Endpoint:
    def __init__(self, app, prefix, name, obj):
        pass

class ServiceEndpoint(Endpoint):
    __rpc__ = False

    def __init__(self, app, prefix, name, service):
        self.app = app
        self.name = name
        self.service = service

    def handle_trpc_request(self, route, request):
        second = route.head
        if not second:
            if request.path[-1] != '/':
                raise HTTPResponse('303 put a / on the end', [('Location', route.prefix+'/')], [])
            return self.describe_trpc_endpoint(embed=True)
        elif not second.startswith('_'):
            s = self.service(self.app, route, request)
            attr = getattr(s, second)

            if getattr(attr, '__rpc__', True):
                if isinstance(attr, (types.FunctionType, types.MethodType)):
                    if request.method == 'POST':
                        data = request.unwrap_arguments()
                        if not data: data = {}
                        return attr(**data)

    def describe_trpc_endpoint(self, embed):
        methods = {}
        for key, m in self.service.__dict__.items():
            if getattr(m, '__rpc__', not key.startswith('_')):
                if isinstance(m, types.FunctionType):
                    methods[key] = funcargs(m)
        return objects.Service(self.name, links=(), forms=methods, urls=()) 

class Service:
    def __init__(self, app, route, request):
        self.app = app
        self.route = route
        self.request = request
        self.params = dict(request.params)
    
    make_trpc_endpoint = ServiceEndpoint


class NamespaceEndpoint(Endpoint):
    __rpc__ = False

    def __init__(self, app, prefix, name, namespace):
        self.app = app
        self.name = name
        self.namespace = namespace

    def handle_trpc_request(self, route, request):
        first = route.head

        if not first:
            if request.path[-1] != '/':
                raise HTTPResponse('303 put a / on the end', [('Location', route.prefix+'/')], [])
            
            return self.describe_trpc_endpoint(embed=True)

        elif not first.startswith('_'):
            item = self.namespace.get(first)
            if not item:
                raise HTTPResponse('404 not found', (), [b'no'])
            return item.handle_trpc_request(route.advance(), request)

    def describe_trpc_endpoint(self, embed):
        links = []
        forms = {}
        embeds = {}
        urls = {}
        for key, value in self.namespace.items():
            if isinstance(value, Endpoint):
                if isinstance(value, FunctionEndpoint):
                    forms[key] = value.arguments()
                else:
                    links.append(key)
                    urls[key] = "{}/".format(key)
                    if embed:
                        service = value.describe_trpc_endpoint(embed)
                        if service:
                            embeds[key] = service.embed()

        return objects.Namespace(name=self.name, links=links, forms=forms, embeds=embeds, urls=urls)

class Namespace:
    def __init__(self):
        pass

    @staticmethod
    def make_trpc_endpoint(app, prefix,  name, obj):
        out = {}
        p = list(prefix)
        p.append(name)
        for key, value in obj.__dict__.items():
            if not key.startswith("_"):
                o = app.make_endpoint(prefix, key, value)
                out[key] = o
        return NamespaceEndpoint(app, prefix, name, out)

class FunctionEndpoint(Endpoint):
    __rpc__ = False

    def __init__(self, app, prefix, name, fn):
        self.app = app
        self.name = name
        self.fn = fn

    def arguments(self):
        return funcargs(self.fn)

    def handle_trpc_request(self, route, request):
        if request.method == 'GET':
            raise HTTPResponse('405 not allowed', (), [b'no'])
        elif request.method == 'POST':
            data = request.unwrap_arguments()
            if not data: data = {}
            return self.fn(**data)
        
        raise HTTPResponse('405 not allowed', [], [b'no'])

    def describe_trpc_endpoint(self, embed):
        return None

class Route:
    def __init__(self, request, path, index):
        self.request = request
        self.path = path
        self.index = index

    @property
    def prefix(self):
        return "/"+"/".join(self.path[:self.index])

    @property
    def head(self):
        if self.index < len(self.path):
            return self.path[self.index]
        else:
            return ''

    def advance(self):
        return Route(self.request, self.path, self.index+1)

class HTTPResponse(Exception):
    def __init__(self, status, headers, body):
        self.status = status
        self.headers = headers or []
        self.body = body

class HTTPRequest:
    def __init__(self, method, path, params, headers, content_type, data):
        self.method = method
        self.path = path
        self.params = params
        self.headers = headers
        self.content_type = content_type
        self.data = data

    def unwrap_arguments(self):
        data = objects.decode(self.data, self.content_type)
        if data and data['kind'] == 'Request':
            return data['arguments']

class Future(Exception):
    def __init__(self, endpoint, args):
        self.endpoint = endpoint
        self.args = args

class App:
    def __init__(self, name, root):
        self.name = name
        self.endpoints = {}
        self.root = self.make_endpoint((), name, root)

    def make_endpoint(self, prefix, name, obj):
        if hasattr(obj, 'make_trpc_endpoint'):
            e = obj.make_trpc_endpoint(self, prefix, name, obj)
            self.endpoints[obj] = e
            return e
        elif isinstance(obj, dict):
            out = {}
            prefix = list(prefix)
            prefix.append(name)
            for key, value in obj.items():
                o = self.make_endpoint(prefix, key, value)
                out[key] = o
            e = NamespaceEndpoint(self, prefix,  name, out)
            # self.endpoints[obj] = e
            return e
        elif isinstance(obj, (types.FunctionType, types.MethodType)):
            e = FunctionEndpoint(self, prefix, name, obj)
            self.endpoints[obj] = e
            return e

    def schema(self):
        return self.root.describe_trpc_endpoint(embed=True)

    def handle(self, name, obj, route, request):
        if name.startswith('_'):
            return
        elif isinstance(obj, Endpoint):
            return obj.handle_trpc_request(route, request)

    def handle_request(self, request):
        route = Route(request, request.path.lstrip('/').split('/'), 0)
        out = self.handle(self.name, self.root, route, request)

        accept = request.headers.get('accept', objects.CONTENT_TYPE).split(',')
        if isinstance(out, (dict, list, int, float, bool, str)):
            out = objects.Result(out)

        content_type, data = out.encode(accept)
        status = "200 Adequate"
        headers = [("content-type", content_type)]
        return HTTPResponse(status, headers, [data])

    def __call__(self, environ, start_response):
        try:
            method = environ.get('REQUEST_METHOD', '')
            prefix = environ.get('SCRIPT_NAME', '')
            path = environ.get('PATH_INFO', '')
            parameters = parse_qsl(environ.get('QUERY_STRING', ''))

            content_length = environ.get('CONTENT_LENGTH','')
            content_type = environ.get('CONTENT_TYPE','')
            if content_length:
                data = environ['wsgi.input'].read(int(content_length))
                if not data:
                    data = None
            else:
                data = None
            headers = {name[5:].lower():value for name, value in environ.items() if name.startswith('HTTP_')}

            try:
                request = HTTPRequest(method, path, parameters, headers, content_type, data)
                response = self.handle_request(request)

            except HTTPResponse as r:
                response = r

            start_response(response.status, response.headers)
            return response.body
        except (StopIteration, GeneratorExit, SystemExit, KeyboardInterrupt):
            raise
        except Exception as e:
            status = "500 bad"
            response_headers = [("content-type", "text/plain")]

            start_response(status, response_headers, sys.exc_info())
            traceback.print_exc()
            return [traceback.format_exc().encode('utf8')]

    def automain(self, name, port=1729):
        if name != '__main__':
            return
        self.main(port)

    def main(self,port=1729):
        if sys.argv[1:] == ['--schema',]:
            import json
            schema = self.schema()
            obj = schema.embed()
            print(json.dumps(obj, indent=4))
            return

        argv = list()
        for arg in sys.argv[1:]:
           if arg.startswith('--port='):
               port = int(arg[7:])
           else:
               argv.append(arg)

        s = wsgi.WSGIServer(self, port=port, request_handler=wsgi.WSGIRequestHandler)

        try:
           s.start()

           environ = dict(os.environ)
           environ['TRPC_URL'] = s.url

           session = client.Session()
           if argv:
               cli.CLI(session).main(argv, environ)
           else:
               print()
               print(s.url)
               print('Press ^C to exit')

               while True:
                   pass
        except KeyboardInterrupt:
           pass
        finally:
           s.stop()

