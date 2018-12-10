import types
import socket
import traceback
import urllib.request
import sys
import os
import json
import shlex
import threading
import inspect

from urllib.parse import urljoin, urlencode, parse_qsl
from wsgiref.simple_server import make_server, WSGIRequestHandler

CONTENT_TYPE = "application/trpc+json"
def funcargs(m):
    signature = inspect.signature(m)
    args = signature.parameters
    args = [a for a in args if not a.startswith('_')]
    if args and args[0] == 'self': args.pop(0)
    return args

class WSGIServer(threading.Thread):
    class QuietWSGIRequestHandler(WSGIRequestHandler):
        def log_request(self, code='-', size='-'):
            pass

    def __init__(self, app, host="", port=0, request_handler=QuietWSGIRequestHandler):
        threading.Thread.__init__(self)
        self.daemon=True
        self.running = True
        self.server = make_server(host, port, app,
            handler_class=request_handler)

    @property
    def url(self):
        return u'http://%s:%d/'%(self.server.server_name, self.server.server_port)

    def run(self):
        self.running = True
        while self.running:
            self.server.handle_request()

    def stop(self):
        self.running =False
        if self.server and self.is_alive():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(self.server.socket.getsockname()[:2])
                s.send(b'\r\n')
                s.close()
            except IOError:
                import traceback
                traceback.print_exc()
        self.join(5)


class objects:
    """
        wire types:

        all wire types are json objects
        must have 'kind', 'apiVersion', 'metadata' field

        kind is built in or java style name

        metadata may contain
            'id', 'url' ,'collection'
            'links', 'methods', 'embeds'
            'selector', 

        other top level fields include
            value values attribute
            state

    """

    class Wire:
        fields = () # top level field names
        metadata = () # metadata field names
        apiVersion = 'v0'

        @property
        def kind(self):
            return self.__class__.__name__

        def encode(self):
            fields = {k:getattr(self, k) for k in self.fields}
            metadata = {k:getattr(self, k) for k in self.metadata}
            return CONTENT_TYPE, json.dumps(dict(
                kind=self.kind,
                apiVersion=self.apiVersion,
                metadata={} if not metadata else metadata,
                **fields
            ))


    
    class Request(Wire):
        apiVersion = 'v0'
        fields = ('arguments',)
        metadata = ()

        def __init__(self, arguments):
            self.arguments = arguments

    class Response(Wire):
        apiVersion = 'v0'
        fields = ('value',)
        metadata = ()

        def __init__(self, value):
            self.value = value

    class Service(Wire):
        apiVersion = 'v0'
        fields = ('name',)
        metadata = ('links','forms', 'embeds')

        def __init__(self, name, links, forms=(), embeds=()):
            self.name = name
            self.links = links
            self.forms = forms
            self.embeds = embeds

    class Namespace(Wire):
        apiVersion = 'v0'
        fields = ('name', )
        metadata = ('links','forms', 'embeds')

        def __init__(self, name, links, forms=(), embeds=()):
            self.name = name
            self.links = links
            self.forms = forms
            self.embeds = embeds


class Client:
    def __init__(self):
        pass

    class Request:
        def __init__(self, verb, url, data):
            self.verb = verb
            self.url = url
            self.data = data
        
    class Response:
        def __init__(self, base_url, kind, apiVersion, metadata, fields):
            self.base_url = base_url
            self.kind = kind
            self.apiVersion = apiVersion
            self.metadata = metadata
            self.fields = fields


        def __repr__(self):
            return self.kind

        def open_link(self, name):
            links = self.metadata['links']
            if name not in links:
                raise Exception(name)

            url = urljoin(self.base_url, name) + "/"

            return Client.Request('GET', url, None)

        def submit_form(self, name, args):
            links = self.metadata['links']
            forms = self.metadata['forms']
            if name not in forms:
                if name in links:
                    url = urljoin(self.base_url, name)
                    return Client.Request('GET', url, None)
                raise Exception(name)

            url = urljoin(self.base_url, name)
            return Client.Request('POST', url, args)

    def fetch(self, request):
        if isinstance(request, str):
            request = self.Request("GET", request, None)

        data = request.data
        if data is None:
            data = ""
        else:
            content_type, data = objects.Request(data).encode()

        data = data.encode('utf8')

        urllib_request= urllib.request.Request(
            url=request.url,
            data=data,
            method=request.verb,
            headers={'Content-Type': CONTENT_TYPE},
        )

        with urllib.request.urlopen(urllib_request) as fh:
            base_url = fh.url
            obj = json.load(fh)

        kind = obj.pop('kind')
        if kind == 'Response':
            return obj['value']
        apiVersion = obj.pop('apiVersion')
        metadata = obj.pop('metadata')

        return self.Response(base_url, kind, apiVersion, metadata, obj)


class Remote:
    def __init__(self, client, response):
        self.client = client
        self.obj = response

    def __getattr__(self, name):
        if name in self.obj.metadata.get('links',()):
            req = self.obj.open_link(name)
            obj = self.client.fetch(req)
            if isinstance(obj, self.client.Response):
                return Remote(self.client, obj)
            return obj

        def method(**args):
            req = self.obj.submit_form(name, args)
            obj = self.client.fetch(req)
            if isinstance(obj, self.client.Response):
                return Remote(self.client, obj)
            return obj
        return method

def open(endpoint):
    c = Client()
    obj = c.fetch(endpoint)
    return Remote(c, obj)

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

class App:
    def __init__(self, name, namespace):
        self.namespace = namespace
        self.name = name

    def unwrap_request(self, request):
        if request is None:
            return
        request = json.loads(request)
        if request['kind'] == 'Request':
            return request['arguments']


    def handle_func(self, func,  method, prefix, tail, data):
        if method == 'GET':
            raise HTTPResponse('405 not allowed', (), 'no')
        elif method == 'POST':
            print(data)
            data = self.unwrap_request(data)
            print(data)
            if not data: data = {}
            return func(**data)
        
        raise HTTPResponse('405 not allowed', (), 'no')

    def handle_service(self, service, method, prefix, tail, data):
        second = tail.split('/',1)
        second, tail = second[0], (second[1] if second[1:] else "")
        if not second:
            methods = {}
            for name, m in service.__dict__.items():
                if getattr(m, '__rpc__', not name.startswith('_')):
                    methods[name] = funcargs(m)
            return objects.Service(second, links=(), forms=methods) 
        else:
            attr = getattr(service, second)
            return self.handle_func(attr, method, prefix+"/"+second, tail, data)


    def handle_object(self, obj, method, prefix, tail, data):
        if isinstance(obj, types.FunctionType):
            return self.handle_func(obj, method, prefix, tail, data)
        elif isinstance(obj, type) and issubclass(obj, Service):
            return self.handle_service(obj, method, prefix, tail, data)

    def handle(self, method, path, data):

        first = path.split('/',1)
        first, tail = first[0], (first[1] if first[1:] else "")

        if not first:
            links = []
            forms = {}
            for key, value in self.namespace.items():
                if isinstance(value, types.FunctionType):
                    forms[key] = funcargs(value)
                elif isinstance(value, type) and issubclass(value, Service):
                    links.append(key)
            out = objects.Namespace(name=self.name, links=links, forms=forms)
            return out.encode()
        else:
            item = self.namespace.get(first)
            if not item:
                raise HTTPResponse('404 not found', (), 'no')

            out = self.handle_object(item, method, first, tail, data)

            if not isinstance(out, objects.Wire):
                out = objects.Response(out)
                
            return out.encode()

    def __call__(self, environ, start_response):
        try:
            method = environ.get('REQUEST_METHOD', '')
            prefix = environ.get('SCRIPT_NAME', '')
            path = environ.get('PATH_INFO', '').lstrip('/')
            parameters = parse_qsl(environ.get('QUERY_STRING', ''))

            content_length = environ['CONTENT_LENGTH']
            if content_length:
                data = environ['wsgi.input'].read(int(content_length))
                if data:
                    data = data.decode('utf-8')
                else:
                    data = None
            else:
                data = None

            try:
                content_type, response = self.handle(method, path, data)
                status = "200 Adequate"
                response_headers = [("content-type", content_type)]
                response = [response.encode('utf-8'), b'\n']
            except HTTPResponse as r:
                status = r.status
                response_headers = r.headers
                response = [ r.body.encode('utf-8') ]

            start_response(status, response_headers)
            return response
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

       class _CLI(CLI):
           def run(self, argv, environ):
               pass

       argv = list()
       for arg in sys.argv[1:]:
           if arg.startswith('--port='):
               port = int(arg[7:])
           else:
               argv.append(arg)

       s = WSGIServer(self, port=port, request_handler=WSGIRequestHandler)
       s.start()

       environ = dict(os.environ)
       environ['TRPC_URL'] = s.url

       client = Client()

       _CLI(client).main(argv, environ)

       print()
       print(s.url)
       print('Press ^C to exit')

       try:
           while True: pass
       except KeyboardInterrupt:
           pass
       finally:
           s.stop()

class CLI:
    MODES = set((
        'call', 'get', 'list',
        'set', 'update', 'create'
        'delete',   
        'watch', 'exec'
        'help', 'error', 'usage', 'complete', 'version'
    ))

    def __init__(self, client):
        self.client = client

    def main(self, argv, environ):
        if 'COMP_LINE' in environ and 'COMP_POINT' in environ:
            # Bash Line Completion.
            line, offset =  environ['COMP_LINE'], int(environ['COMP_POINT'])
            try:
                import shlex
                prefix = shlex.split(line[:offset])
                # if there's mismatched ''s bail
            except ValueError:
                sys.exit(0)

            prefix = line[:offset].split(' ')
            for o in self.complete(prefix):
                print(o)
            sys.exit(0)

        self.run(argv, environ)

    def complete(self, prefix):
        pass

    def run(self, argv, environ):
        endpoint = os.environ.get("TRPC_URL", "")

        if not endpoint:
            print("Set TRPC_URL first", file=sys.stderr)
            sys.exit(-1)

        mode, path, args = self.parse(argv, environ)

        obj = self.client.fetch(endpoint)

        for p in path[:-1]:
            obj = self.client.fetch(obj.open_link(p))
    
        if path:
            if mode == 'call':
                req = obj.submit_form(path[-1], dict(args))
                obj = self.client.fetch(req) 
        print(obj)
        return

    def parse(self, argv, environ):
        mode = "call"
        if argv and argv[0] in self.MODES:
            mode = argv.pop(0)

        path = ""
        app_args = []
        args = []
        
        if argv and not argv[0].startswith('--'):
            path = argv.pop(0).split(':')

        flags = True
        for arg in argv:
            name, value = None, None
            if flags and arg == '--':
                flags = False
                continue
            if flags and arg.startswith('--'):
                if '=' in arg:
                    name, value = arg[2:].split('=', 1)
                else:
                    name, value = arg[2:], None
            else:
                name, value = None, arg
            args.append((name, value))
        return mode, path, args

    def automain(name):
        if name == '__main__':
            client = Client()
            cli = CLI(client)
            cli.main(sys.argv[1:], os.environ)

CLI.automain(__name__)
    
