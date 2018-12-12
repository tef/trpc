import types
import traceback
import sys
import os
import json
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
    pass


class HTTPResponse(Exception):
    def __init__(self, status, headers, body):
        self.status = status
        self.headers = headers or []
        self.body = body

class HTTPRequest:
    def __init__(self, method, path, params, headers, data):
        self.method = method
        self.path = path
        self.params = params
        self.headers = headers
        self.data = data

    def unwrap_arguments(self):
        if self.data is None:
            return
        data = json.loads(self.data.decode('utf-8'))
        if data['kind'] == 'Request':
            return data['arguments']

class App:
    def __init__(self, name, root):
        self.name = name
        self.root = root

    def handle_func(self, func, prefix, tail, request):
        if request.method == 'GET':
            raise HTTPResponse('405 not allowed', (), [b'no'])
        elif request.method == 'POST':
            data = request.unwrap_arguments()
            if not data: data = {}
            return func(**data)
        
        raise HTTPResponse('405 not allowed', [], [b'no'])

    def handle_service(self, service,  prefix, tail, request):
        second = tail.split('/',1)
        second, tail = second[0], (second[1] if second[1:] else "")
        if not second:
            if request.path[-1] != '/':
                raise HTTPResponse('303 put a / on the end', [('Location', prefix+'/')], [])

            methods = {}
            for name, m in service.__dict__.items():
                if getattr(m, '__rpc__', not name.startswith('_')):
                    methods[name] = funcargs(m)
            return objects.Service(second, links=(), forms=methods) 
        else:
            attr = getattr(service, second)
            return self.handle_func(attr, prefix+"/"+second, tail, request)


    def handle_object(self, name, obj,  prefix, tail, request):
        if isinstance(obj, types.FunctionType):
            return self.handle_func(obj, prefix, tail, request)
        elif isinstance(obj, type) and issubclass(obj, Service):
            return self.handle_service(obj, prefix, tail, request)
        elif isinstance(obj, dict):
            return self.handle_namespace(name, obj, prefix, tail, request)
    
    def handle_namespace(self, name,  obj, prefix, tail, request):
        first = tail.split('/',1)
        first, tail = first[0], (first[1] if first[1:] else "")

        if not first:
            if request.path[-1] != '/':
                raise HTTPResponse('303 put a / on the end', [('Location', prefix+'/')], [])
            links = []
            forms = {}
            for key, value in obj.items():
                if isinstance(value, types.FunctionType):
                    forms[key] = funcargs(value)
                elif isinstance(value, type) and issubclass(value, Service):
                    links.append(key)
                elif isinstance(value, dict):
                    links.append(key)

            return objects.Namespace(name=name, links=links, forms=forms)
        else:
            item = obj.get(first)
            if not item:
                raise HTTPResponse('404 not found', (), [b'no'])

            return self.handle_object(first, item, prefix+'/'+first, tail, request)

    def handle(self, request):
        out = self.handle_object(self.name, self.root, '', request.path.lstrip('/'), request)

        if not isinstance(out, objects.Wire):
            out = objects.Response(out)
    
        content_type, data = out.encode()
        status = "200 Adequate"
        headers = [("content-type", objects.CONTENT_TYPE)]
        body = [data.encode('utf-8'), b'\n']
        return HTTPResponse(status, headers, body)

    def __call__(self, environ, start_response):
        try:
            method = environ.get('REQUEST_METHOD', '')
            prefix = environ.get('SCRIPT_NAME', '')
            path = environ.get('PATH_INFO', '')
            parameters = parse_qsl(environ.get('QUERY_STRING', ''))

            content_length = environ['CONTENT_LENGTH']
            if content_length:
                data = environ['wsgi.input'].read(int(content_length))
                if not data:
                    data = None
            else:
                data = None
            headers = {name[5:].lower():value for name, value in environ.items() if name.startswith('HTTP_')}

            try:
                request = HTTPRequest(method, path, parameters, headers, data)
                response = self.handle(request)

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

