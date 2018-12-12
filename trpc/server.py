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

def rpc():
    def _decorate(fn):
        fn.__rpc__ = True
        return fn
    return _decorate

class Service:
    def __init__(self, app, route, request):
        self.app = app
        self.route = route
        self.request = request

    def handle_trpc_request(app, service, route, request):
        second = route.head
        if not second:
            if request.path[-1] != '/':
                raise HTTPResponse('303 put a / on the end', [('Location', route.prefix+'/')], [])

            methods = {}
            for name, m in service.__dict__.items():
                if getattr(m, '__rpc__', not name.startswith('_')):
                    methods[name] = funcargs(m)
            return objects.Service(second, links=(), forms=methods) 
        else:
            s = service(app, route, request)
            attr = getattr(s, second)
            return app.handle_func(attr, route.advance(), request)

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

class App:
    def __init__(self, name, root):
        self.name = name
        self.root = root

    def schema(self):
        return self.build_namespace(self.name, self.root, embed=True)

    def build_namespace(self, name, obj, embed=False):
        links = []
        forms = {}
        embeds = {}
        for key, value in obj.items():
            if isinstance(value, types.FunctionType):
                forms[key] = funcargs(value)
            elif isinstance(value, type) and issubclass(value, Service):
                links.append(key)
            elif isinstance(value, dict):
                links.append(key)
                if embed:
                    namespace = self.build_namespace(key, value, embed=embed)
                    embeds[key] = namespace.dump()

        return objects.Namespace(name=name, links=links, forms=forms, embeds=embeds)

    def handle(self, name, obj, route, request):
        if isinstance(obj, dict):
            return self.handle_dict(name, obj, route, request)
        elif isinstance(obj, type) and issubclass(obj, Service):
            return obj.handle_trpc_request(self, obj, route, request)
        elif isinstance(obj, types.FunctionType):
            return self.handle_func(obj, route, request)
    
    def handle_func(self, func, route, request):
        if request.method == 'GET':
            raise HTTPResponse('405 not allowed', (), [b'no'])
        elif request.method == 'POST':
            data = request.unwrap_arguments()
            if not data: data = {}
            return func(**data)
        
        raise HTTPResponse('405 not allowed', [], [b'no'])

    def handle_dict(self, name,  obj, route, request):
        first = route.head

        if not first:
            if request.path[-1] != '/':
                raise HTTPResponse('303 put a / on the end', [('Location', route.prefix+'/')], [])
            
            return self.build_namespace(name, obj)
        else:
            item = obj.get(first)
            if not item:
                raise HTTPResponse('404 not found', (), [b'no'])

            return self.handle(first, item, route.advance(), request)


    def handle_request(self, request):
        route = Route(request, request.path.lstrip('/').split('/'), 0)
        out = self.handle(self.name, self.root, route, request)

        accept = request.headers.get('accept', objects.CONTENT_TYPE).split(',')

        content_type, data = objects.encode(out, accept)
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

        if sys.argv[1:] == ['--schema',]:
            import json
            schema = self.schema()
            obj = schema.dump()
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

