import types
import traceback
import sys
import os
import inspect

from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlencode, parse_qsl
from functools import singledispatch
from typing import List, Tuple, Dict, Any

def type_to_kind(cls):
    if cls == str:
        return "string"
    elif cls == list or cls == tuple:
        return ["list"]
    elif cls == float:
        return "float"
    elif cls == int:
        return "integer"
    elif cls == bool:
        return "boolean"
    elif cls == bytes or cls == bytearray:
        return "bytestring"
    elif cls == set:
        return ["set"]
    elif cls == datetime:
        return "datetime"
    elif cls == timedelta:
        return "duration"
    elif cls == dict:
        return ["object"]
    elif cls == Any:
        return "any"
    elif cls == List or cls == Tuple:
        return ["list"]
    elif cls == List[str]:
        return ["list","str"]
    elif cls == List[int]:
        return ["list","integer"]
    return "json"

from . import wire, client, cli, wsgi

def funcargs(m):
    signature = inspect.signature(m)
    args = {}
    for name, p in signature.parameters.items():
        if name == 'self': continue
        if name.startswith('_') and p.default == p.empty: raise Exception('no')
        args[name] = None if p.annotation == p.empty else type_to_kind(p.annotation)
    return args

def call_function(fn, route, request):
    data = request.unwrap_arguments()
    return fn(**data) if data else fn()

def call_raw_function(fn, route, request):
    data = request.unwrap_arguments()
    return fn(data) if data else fn()

def argspec_for_kind(kind):
    if kind is None: return "json"
    if kind == "any": return "json_or_scalar"
    if kind == "string": return "string"
    if kind[0] == "list":
        if kind[1] == "string": return "str*"
        if kind[1] == "integer": return "int*"
        if kind[1] == "bool": return "*"
        if kind[1] == "any": return "json_or_scalar*"
        return "json*"

    return "json"

def rpc(raw_args=None, command_line=None):
    def _decorate(fn):
        if raw_args:
            fn.__trpc__ = call_raw_function
            fn.arguments = None
            fn.command_line = command_line
        else:
            fn.__trpc__ = call_function
            arguments = funcargs(fn)
            fn.arguments = arguments
            if command_line:
                fn.command_line = command_line
            else:
                argspec = {}
                if len(arguments) > 1:
                    for k,v in fn.arguments.items():
                        kind = argspec_for_kind(v)
                        argspec[k] = "--{}".format(kind)
                elif len(arguments) == 1:
                    for k,v in fn.arguments.items():
                        kind = argspec_for_kind(v)
                        argspec[k] = kind
                fn.command_line = argspec
        return fn
    return _decorate

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


class Redirect:
    def __init__(self, target):
        self.target = target

class Future:
    def __init__(self, target, args):
        self.target = target
        self.args = args

class Cursor:
    def __init__(self, values, target, args):
        self.values = values
        self.target = target
        self.args = args

class Endpoint:
    def __init__(self, app, prefix, name, obj):
        pass

    def route_for(self, obj):
        pass

    def endpoint_for(self):
        return ()

class ServiceEndpoint(Endpoint):
    def __init__(self, app, prefix, name, service):
        self.prefix = prefix
        self.app = app
        self.name = name
        self.service = service

    def route_for(self, obj):
        route = list(self.prefix)
        if obj == self.service or isinstance(obj, self.service):
            route.append("")
            return route

        route.append(obj.__name__)
        obj = obj.__self__
        if obj == self.service or isinstance(obj, self.service):
            return route

    def endpoint_for(self):
        return (self.service,)

    def handle_trpc_request(self, route, request):
        second = route.head
        if not second:
            if request.url[-1] != '/':
                raise wire.HTTPResponse('303 put a / on the end', [('Location', route.prefix+'/')], [])
            return self.describe_trpc_endpoint(embed=True)
        elif not second.startswith('_'):
            s = self.service(self.app, route, request)
            attr = getattr(s, second)

            if isinstance(attr, (types.FunctionType, types.MethodType)):
                handler = getattr(attr, '__trpc__', None)
                if handler and request.method == 'POST':
                    return handler(attr, route, request)

    def describe_trpc_endpoint(self, embed):
        links = []
        urls = {}
        embeds={}
        for key, m in self.service.__dict__.items():
            if not key.startswith('_') and hasattr(m, '__trpc__') and isinstance(m, types.FunctionType):
                links.append(key)
                if embed:
                    embeds[key] = wire.Procedure(m.arguments, m.command_line).embed()

        return wire.Service(name=self.name, links=links, embeds=embeds, urls=urls)


class Service:
    def __init__(self, app, route, request):
        self.app = app
        self.route = route
        self.request = request
        self.params = dict(request.params)
    
    make_trpc_endpoint = ServiceEndpoint


class NamespaceEndpoint(Endpoint):

    def __init__(self, app, prefix, name, cls, entries):
        self.app = app
        self.prefix = prefix
        self.name = name
        self.cls = cls
        self.namespace = entries

    def endpoint_for(self):
        if self.cls:
            return (self.cls,)
        return ()

    def route_for(self, obj):
        route = list(self.prefix)
        if obj == self.namespace:
            route.append("")
            return route

        if obj in self.namespace:
            route.append(obj.__name__)
            return route

    def handle_trpc_request(self, route, request):
        first = route.head

        if not first:
            if request.url[-1] != '/':
                raise wire.HTTPResponse('303 put a / on the end', [('Location', route.prefix+'/')], [])
            
            return self.describe_trpc_endpoint(embed=True)

        elif not first.startswith('_'):
            item = self.namespace.get(first)
            if not item:
                raise wire.HTTPResponse('404 not found', (), [b'no'])
            return item.handle_trpc_request(route.advance(), request)

    def describe_trpc_endpoint(self, embed):
        links = []
        forms = {}
        embeds = {}
        urls = {}
        for key, value in self.namespace.items():
            if isinstance(value, Endpoint):
                links.append(key)
                if not isinstance(value, FunctionEndpoint):
                    urls[key] = "{}/".format(key)
                if embed:
                    service = value.describe_trpc_endpoint(embed)
                    if service:
                        embeds[key] = service.embed()

        return wire.Namespace(name=self.name, links=links, embeds=embeds, urls=urls)

class Namespace:
    def __init__(self):
        pass

    @staticmethod
    def make_trpc_endpoint(app, prefix,  name, obj):
        out = app.make_child_endpoints(prefix, name, {k:v for k,v in obj.__dict__.items()})
        return NamespaceEndpoint(app, prefix, name, obj, entries=out)

class FunctionEndpoint(Endpoint):
    def __init__(self, app, prefix, name, fn):
        self.app = app
        self.name = name
        self.fn = fn

    def arguments(self):
        return self.fn.arguments

    def endpoint_for(self):
        return (self.fn,)

    def route_for(self, obj):
        route = list(self.prefix)
        if obj == self.service or isinstance(obj, self.service):
            return route

        route.append(obj.__name__)
        obj = obj.__self__
        if obj == self.service or isinstance(obj, self.service):
            return route

    def handle_trpc_request(self, route, request):
        if request.method == 'GET':
            return self.describe_trpc_endpoint()

        elif request.method == 'POST':
            handler = getattr(attr, '__trpc__', None)
            if handler:
                return handler(attr, route, request)
        
        raise wire.HTTPResponse('405 not allowed', [], [b'no'])

    def describe_trpc_endpoint(self, embed):
        return wire.Procedure(self.fn.arguments, self.fn.command_line)

class CollectionEndpoint(Endpoint):
    def __init__(self, app, prefix, name,  model):
        self.prefix = prefix
        self.app = app
        self.name = name
        self.model = model

    def route_for(self):
        route = list(self.prefix)
        if obj == self.model:
            route.append("")
            return route

    def endpoint_for(self):
        return (self.model,)

    def handle_trpc_request(self, route, request):
        method = route.head

        if not method:
            if request.path[-1] != '/':
                raise HTTPResponse('303 put a / on the end', [('Location', route.prefix+'/')], [])
            return self.describe_collection()

        route = route.advance()
        key = route.head
        route = route.advance()
        obj_method = route.head
        route = route.advance()

        if method.startswith('_') or obj_method.startswith('_'):
            return

        print(method, key, obj_method)

        if method == 'id':
            if key and obj_method:
                data = request.unwrap_arguments()
                return self.call_entry(key, method, data)
            elif key:
                return self.describe_entry(key)
        elif method == 'list':
            selector = params.get('where')
            cursor = params.get('state')
            return self.get_list(selector, cursor)
        elif method == 'create':
            data = request.unwrap_arguments()
            return self.create_entry(data)
        elif method == 'set':
            data = request.unwrap_arguments()
            if key:
                return self.set_key(key, data)
            else:
                selector = params.get('where')
                return self.set_list(selector, data)
        elif method == 'update':
            data = request.unwrap_arguments()
            if key:
                return self.update_key(key, data)
            else:
                selector = params.get('where')
                return self.update_list(selector, data)
        elif method == 'delete':
            if key:
                return self.delete(key)
            else:
                selector = params.get('where')
                return self.delete_list(selector)
        elif method == 'watch':
            if key:
                return self.watch_key(key, data)
            else:
                selector = params.get('where')
                return self.watch_list(selector)

    def describe_trpc_endpoint(self, embed=True):
        return self.describe_collection()

    def describe_collection(self): 
        pass
    def describe_entry(self, key): 
        pass
    def create_entry(self, data): 
        pass
    def update_entry(self, key, data): 
        pass
    def set_entry(self, key, data): 
        pass
    def delete_entry(self, key): 
        pass
    def watch_entry(self, key): 
        pass
    def call_entry(self, key, method, args): 
        pass
    def get_list(self, selector, cursor=None): 
        pass
    def delete_list(self, selector): 
        pass
    def set_list(self, selector, value): 
        pass
    def update_list(self, selector, value): 
        pass
    def watch_list(self, selector, cursor=None): 
        pass

class App:
    def __init__(self, name, root):
        self.name = name
        self.endpoints = {}
        self.root = self.make_endpoint((), name, root)

    def make_endpoint(self, prefix, name, obj):
        if isinstance(name, type) and issubclass(obj, Endpoint):
            e = obj(self, prefix, name, obj)
        elif hasattr(obj, 'make_trpc_endpoint'):
            e = obj.make_trpc_endpoint(self, prefix, name, obj)
        elif isinstance(obj, dict):
            out = self.make_child_endpoints(prefix, name, obj)
            class _Namespace(Namespace):
                pass
            e = NamespaceEndpoint(self, prefix,  name, _Namespace, out)
        elif isinstance(obj, (types.FunctionType, types.MethodType)):
            e = FunctionEndpoint(self, prefix, name, obj)
        else:
            raise Exception(obj)
            return

        for o in e.endpoint_for():
            self.endpoints[o] = e
        return e

    def make_child_endpoints(self, prefix, name, entries):
        out = {}
        for key, value in entries.items():
            if key.startswith('_'): continue
            p = list(prefix)
            p.append(key)
            o = self.make_endpoint(p, key, value)
            out[key] = o
        return out

    def route_for(self, obj):
        endpoint = self.endpoints.get(obj)
        if endpoint is not None:
            return endpoint.route_for(obj) 

        instance = getattr(obj, '__self__', None)
        if instance is not None:
            endpoint = self.endpoints.get(instance)
            if endpoint is not None:
                return endpoint.route_for(obj) 

            cls = getattr(instance, '__class__', None)
            endpoint = self.endpoints.get(cls)
            if endpoint is not None:
                return endpoint.route_for(obj) 

        cls = getattr(obj, '__class__', None)
        endpoint = self.endpoints.get(cls)
        if endpoint is not None:
            return endpoint.route_for(obj) 

    def schema(self):
        return self.root.describe_trpc_endpoint(embed=True)

    def handle_request(self, request):
        route = Route(request, request.url.lstrip('/').split('/'), 0)
        
        out = self.root.handle_trpc_request(route, request)
        if isinstance(out, Redirect):
            route = self.route_for(out.target)
            url = "/{}".format("/".join(route))
            status = "303 TB"
            headers = [("Location", url)]
            return wire.HTTPResponse(status, headers, [])

        if isinstance(out, Future):
            route = self.route_for(out.target)
            url = "/{}".format("/".join(route))
            out = wire.FutureResult(url, out.args)
        elif isinstance(out, Cursor):
            if out.target:
                route = self.route_for(out.target)
                url = "/{}".format("/".join(route))
            else:
                url = None
            out = wire.ResultSet(out.values, url, out.args)
        else:
            out = wire.wrap(out)

        return out


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
            accept = headers.get('accept', wire.CONTENT_TYPE).split(',')

            try:
                request = wire.HTTPRequest(method, path, parameters, headers, content_type, data, None)
                out = self.handle_request(request)

                content_type, data = out.encode(accept)
                status = "200 Adequate"
                headers = [("content-type", content_type)]
                response = wire.HTTPResponse(status, headers, [data])
            except wire.HTTPResponse as r:
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
        serve = False
        if 'COMP_LINE' not in os.environ and 'COMP_POINT' not in os.environ:
            argv = list()
            for arg in sys.argv[1:]:
                if arg.startswith('--port='):
                    port = int(arg[7:])
                elif arg == "--serve":
                    serve = True
                else:
                   argv.append(arg)

            if sys.argv[1:] == ['--schema',]:
                import json
                schema = self.schema()
                obj = schema.embed()
                print(json.dumps(obj, indent=4))
                return
        else:
            argv = sys.argv[1:]

        if not serve:
            schema = self.schema().embed()
            environ = dict(os.environ)
            environ['TRPC_URL'] = wire.Request('get', '/', None, schema)

            session = AppSession(self)
            return cli.CLI(session).main(argv, environ)


        s = wsgi.WSGIServer(self, port=port, request_handler=wsgi.WSGIRequestHandler)

        try:
            s.start()
            url = s.url
            schema = None

            environ = dict(os.environ)
            environ['TRPC_URL'] = wire.Request('get', url, None, schema)
           
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

class AppSession(client.Session):
    def __init__(self, app):
        self.app = app

    def raw_request(self, request, base_url):
        if request.cached:
            out = wire.decode_object(request.cached)
            url = urljoin(base_url, request.path)
            return url, out
        else:
            request = request.make_http(base_url)
            out = self.app.handle_request(request)
            return request.url, out
