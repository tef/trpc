import threading
import socket
import traceback
import sys
import json

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
        metadata may contain 'id', 'url'

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
            return "text/json", json.dumps(dict(
                kind=self.kind,
                apiVersion=self.apiVersion,
                metadata={} if not metadata else metadata,
                **fields
            ))

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
        out = objects.Response( dict(method=method, path=path, data=data))
        return out.encode()

    def __call__(self, environ, start_response):
        try:
            method = environ.get('REQUEST_METHOD', '')
            prefix = environ.get('SCRIPT_NAME', '')
            path = environ.get('PATH_INFO', '')
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



