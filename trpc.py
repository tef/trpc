import socket
import traceback
import urllib.request
import sys
import os
import json
import shlex
import threading

from urllib.parse import urljoin, urlencode, parse_qsl
from wsgiref.simple_server import make_server, WSGIRequestHandler

def funcargs(m):
    args =  m.__code__.co_varnames[:m.__code__.co_argcount]
    args = [a for a in args if not a.startswith('_')]
    if args and args[0] == 'self': args.pop(0)
    return args

class Server(threading.Thread):
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

class Meta(type):
    @classmethod
    def __prepare__(metacls, name, bases, **args):
        """ Called before class definition to return class namespace"""
        m = metacls.Methods()
        for name in metacls.Methods.__dict__:
            if not name.startswith('__'):
                setattr(m, name, getattr(m, name))
        return m.__dict__

    def __new__(metacls, name, bases, attrs, **args):
        """ Called after class definition to return a class object """
        attrs = dict(attrs)
        for k, v in metacls.Methods.__dict__.items():
            if v and attrs.get(k) == v:
                attrs.pop(k)

        return super().__new__(metacls, name, bases, attrs)

    class Methods:
        def rpc(self):
            def _decorate(fn):
                return fn
            return _decorate

class Service(metaclass=Meta):
    pass

class Model(metaclass=Meta):
    pass


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
            return "application/json", json.dumps(dict(
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

    class Namespace(Wire):
        apiVersion = 'v0'
        fields = ('members',)
        metadata = ()

        def __init__(self, members ):
            self.members = members



class App:
    def __init__(self, namespace):
        self.namespace = namespace

    def handle(self, method, path, data):

        first = path.split('/',1)
        first, tail = first[0], first[1:]

        if not first:
            out = objects.Namespace(list(self.namespace.keys()))
            return out.encode()
        else:
            item = self.namespace.get(first)
            out = objects.Response( dict(method=method, first=first, path=path, data=data))
            if method == 'GET':
                pass
            elif method == 'POST':
                pass
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
                    data = json.loads(data.decode('utf-8'))
                else:
                    data = None

            else:
                data = None

            content_type, response = self.handle(method, path, data)

            status = "200 Adequate"
            response_headers = [("content-type", content_type)]
            start_response(status, response_headers)
            return [response.encode('utf-8'), b'\n']
        except (StopIteration, GeneratorExit, SystemExit, KeyboardInterrupt):
            raise
        except Exception as e:
            status = "500 bad"
            response_headers = [("content-type", "text/plain")]

            start_response(status, response_headers, sys.exc_info())
            return [traceback.format_exc().encode('utf8')]

    def automain(self, name):
       if name == '__main__':
            port = int(sys.argv[1]) if sys.argv[1:] else 1729
            s = Server(self, port=port)
            s.start()
            print(s.url)
            try:
                while True: pass
            except KeyboardInterrupt:
                pass
            finally:
                s.stop()


class Client:
    def __init__(self):
        pass

    class Request:
        def __init__(self, verb, url, data):
            self.verb = verb
            self.url = url
            self.data = data

        def urllib_request(self):
            data = self.data
            if data is None:
                data = {}
            data = json.dumps(data).encode('utf8')

            return urllib.request.Request(
                url=self.url,
                data=data,
                method=self.verb,
                headers={'Content-Type':'application/json'},
            )

    class Namespace:
        def __init__(self, obj, build_request):
            self.members = obj['members']

    class Service:
        def __init__(self, obj, build_request):
            self._obj = obj
                
    def urllib_request(self, verb, request):
        if isinstance(request, str):
            request = self.Request(verb, request, None)
        return request.urllib_request()

    def unwrap_response(self, fh):
        base_url = fh.url

        def build_request(method, url, data):
            url = urljoin(base_url, url)
            return self.Request(method, url, data)


        obj = json.load(fh)
        if obj['kind'] == 'Response':
            return obj['value']
        if obj['kind'] == 'Namespace':
            return self.Namespace(obj, build_request)
        if obj['kind'] == 'Service':
            return self.Namespace(obj, build_request)

    def fetch(self, request):
        r = self.urllib_request('GET', request)
        with urllib.request.urlopen(r) as response:
           return self.unwrap_response(response)

    def call(self, request):
        r = self.urllib_request('POST', request)
        with urllib.request.urlopen(r) as response:
           return self.unwrap_response(response)

    def list(self, request):
        pass

class CLI:
    MODES = set((
        'call', 'get', 'list',
        'set', 'update', 'create'
        'delete', 
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

        endpoint = os.environ.get("TRPC_URL", "")
        if not endpoint:
            print("Set TRPC_URL first", file=sys.stderr)
            sys.exit(-1)

        mode, path, args = self.parse(argv, environ)

        print(self.client.fetch(endpoint))


    def parse(self, argv, environ):
        mode = "call"
        if argv and argv[0] in self.MODES:
            mode = argv.pop(0)

        path = ""
        app_args = []
        args = []
        
        if argv and not argv[0].startswith('--'):
            path = argv.pop(0)

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
            if name in self.parser.argspec:
                app_args.append((name, value))
            else:
                args.append((name, value))
        return mode, path, args

    def automain(name):
        if name == '__main__':
            client = Client()
            cli = CLI(client)
            cli.main(sys.argv[1:], os.environ)

CLI.automain(__name__)
    
