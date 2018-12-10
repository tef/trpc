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

from . import objects
from .cli import CLI
from .client import Client

CONTENT_TYPE = objects.CONTENT_TYPE

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
    def __init__(self, verb, url, params, headers, body):
        self.verb = verb
        self.url = url
        self.params = params
        self.headers = headers
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
            data = self.unwrap_request(data)
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

       argv = list()
       for arg in sys.argv[1:]:
           if arg.startswith('--port='):
               port = int(arg[7:])
           else:
               argv.append(arg)

       s = WSGIServer(self, port=port, request_handler=WSGIRequestHandler)
       try:
           s.start()

           environ = dict(os.environ)
           environ['TRPC_URL'] = s.url

           client = Client()
           if argv:
               CLI(client).main(argv, environ)
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

