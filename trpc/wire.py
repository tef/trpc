"""
wire types:

all wire types are json objects and must have 'kind', 'apiVersion', 'metadata' fields

kind is built in or java style name
apiVersion is a string, without any ordering or semantic information defined.

metadata may contain
    'id', 'url' ,'collection'
    'routes', 'methods', 'embeds'
    'selector', 

other top level fields include
    'value' 'values' 'attributes' 'arguments' 'state'

"""

import json
from urllib.parse import urljoin, urlencode

CONTENT_TYPE = "application/trpc+json"

def decode_file(obj, content_type):
    if not obj:
        return None
    if content_type == CONTENT_TYPE:
        return decode_object(json.load(obj))

def decode_bytes(obj, content_type):
    if not obj:
        return None
    if content_type == CONTENT_TYPE:
        return decode_object(json.loads(obj.decode('utf-8')))

def decode_object(obj):
    kind = obj.get('kind')
    return Message.init_from_dict(obj)

def wrap(out):
    if not isinstance(out, Message):
        out = Result(out)
    return out

def encode(out, accept):
    return wrap(out).encode(accept)

class HTTPResponse(Exception):
    def __init__(self, status, headers, body):
        self.status = status
        self.headers = headers or []
        self.body = body

class HTTPRequest:
    def __init__(self, method, url, params, headers, content_type, data, cached):
        self.method = method
        self.url = url
        self.params = params
        self.headers = headers
        self.content_type = content_type
        self.data = data
        self.cached = cached

    def unwrap_arguments(self):
        data = decode_bytes(self.data, self.content_type)
        if isinstance(data, Arguments):
            return data.values

    def unwrap_param(self, name):
        p = self.params.get(name)
        if p:
            return json.loads(p)

class Request:
    def __init__(self, mode, path, params, args, cached):
        self.mode = mode
        self.path = path
        self.params = params
        self.args = args
        self.cached = cached

    def make_http(self, base_url):
        method = "GET" if self.mode in ("get","walk", "list") else "POST"
        if self.args is not None:
            content_type, data = Arguments(self.args).encode()
        else:
            content_type, data = None, b""

        url = urljoin(base_url, self.path)
        if self.params:
            params = {k:json.dumps(v) for k,v in self.params.items()}
        else:
            params = {}

        return HTTPRequest(
            method = method,
            url = url,
            data = data, 
            params = params,
            headers = {'Accept': CONTENT_TYPE},
            content_type = content_type,
            cached = self.cached
        )


class Message:
    Kinds = {}
    Fields = () # top level field names
    Metadata = () # metadata field names
    apiVersion = 'v0'
    enumerable = False

    # subclass hook
    def __init_subclass__(cls):
        cls.Kinds[cls.__name__] = cls

    # class methd ctor from obj
    @classmethod
    def init_from_dict(cls, obj):
        obj = dict(obj)
        kind = obj.pop('kind')
        apiVersion = obj.pop('apiVersion')
        metadata = obj.pop('metadata')
        Kind = cls.Kinds.get(kind)
        if not Kind: return
        self = Kind.__new__(Kind)
        for name in Kind.Fields:
            value = obj.get(name)
            setattr(self, name, value)
        for name in Kind.Metadata:
            value = metadata.get(name)
            setattr(self, name, value)
        return self


    def __init__(self, *args, **kwargs):
        names = list()
        names.extend(self.Fields)
        names.extend(self.Metadata)
        for value in args:
            name = names.pop(0)
            setattr(self, name, value)
        for name in names:
            value = kwargs.get(name)
            setattr(self, name, value)

    @property
    def kind(self):
        return self.__class__.__name__

    def format(self):
        fields = {k:getattr(self, k) for k in self.Fields}
        return "{}: {}".format(self.kind, fields)

    def embed(self):
        fields = {k:getattr(self, k) for k in self.Fields}
        metadata = {k:getattr(self, k) for k in self.Metadata}
        return dict(
            kind=self.kind,
            apiVersion=self.apiVersion,
            metadata={} if not metadata else metadata,
            **fields
        )

    def encode(self, accept=None):
        data = json.dumps(self.embed())
        return CONTENT_TYPE, data.encode('utf-8')

    def get_routes(self):
        return ()


class Navigable:
    def walk(self, name):
        if name not in self.routes:
            raise Exception(name)

        url = self.urls.get(name, name)

        cached = self.embeds.get(name)

        return Request('walk', url, {}, None, cached)
    
    def get_routes(self):
        return self.routes

class Enumerable:
    def request_next(self, limit=None):
        pass
    def enumerate(self):
        pass
class Invokable:
    def call(self, args):
        pass
class Format:
    def format(self):
        return self

class Result(Format, Message):
    apiVersion = 'v0'
    Fields = ('value',)
    Metadata = ()

    def format(self):
        return str(self.value)

class FutureResult(Message):
    apiVersion = 'v0'
    Fields = ()
    Metadata = ('url', 'args', 'wait_seconds')

    def make_request(self):
        return Request('call', self.url, {}, self.args, None)

class Arguments(Message):
    apiVersion = 'v0'
    Fields = ('values',)
    Metadata = ()

class Procedure(Invokable, Message):
    apiVersion = 'v0'
    Fields = ('arguments','command_line')
    Metadata = ()

    def call(self, arguments):
        url = ''

        if self.arguments is not None:
            args = {}
            for key in self.arguments:
                args[key] = arguments.pop(key, None)
            if arguments:
                raise Exception("unkown args: {}".format(", ".join(arguments.keys())))
        elif isinstance(arguments, dict):
            args = arguments
        else:
            args = dict(arguments)
        if None in args: raise Exception('No')

        return Request('call', url, {}, args, None)

class Service(Navigable, Message):
    apiVersion = 'v0'
    Fields = ('name',)
    Metadata = ('routes', 'embeds', 'urls')

class Namespace(Navigable, Message):
    apiVersion = 'v0'
    Fields = ('name', )
    Metadata = ('routes', 'embeds', 'urls')

class ResultSet(Enumerable, Message):
    apiVersion = 'v0'
    Fields = ('values',)
    Metadata = ('next','args',)
    def enumerate(self):
        return [Result(v) for v in self.values]
    def request_next(self, limit=None):
        if self.next:
            query = dict(limit=limit)
            return Request('call', self.next, query, self.args, None)

class Model(Message):
    apiVersion = 'v0'
    Fields = ('name', )
    Metadata = ('key','create', 'indexes', 'routes', 'embeds', 'urls')

    def get_entry(self, key):
        url = 'id/{}'.format(key)
        return Request('get', url, {}, None, None)

    def create_entry(self, args):
        url = 'create'
        return Request('create', url, {}, args, None)

    def delete_entry(self, key):
        url = 'delete/{}'.format(key)
        return Request('delete', url, {}, None, None)

    def set_entry(self, key, args):
        url = 'set/{}'.format(key)
        return Request('set', url, {}, args, None)

    def update_entry(self, key, args):
        url = 'update/{}'.format(key)
        return Request('update', url, {}, args, None)

    def watch_entry(self, key):
        pass

    def get_where(self, selector, limit=None):
        query = dict(selector=selector, limit=limit)
        return Request('list', 'list', query, None, None)

    def delete_where(self, selector):
        pass

    def watch_where(self, selector):
        pass

class Entry(Format, Message):
    apiVersion = 'v0'
    Fields = ('attributes', )
    Metadata = ('collection', 'routes', 'embeds', 'urls')

    def format(self):
        return self.attributes

class EntrySet(Enumerable, Message):
    apiVersion = 'v0'
    Fields = ('items', )
    Metadata = ('next', 'selector', 'state')
    def enumerate(self):
        return [decode_object(i) for i in self.items]
        # todo - shared metadata
    def request_next(self, limit=None):
        if self.next is not None:
            query = dict(selector=self.selector, state=self.state, limit=limit)
            return Request('list', self.next, query, None, None)

# Stream - one way out

# Channel - two way

# Terminal - two way + result

# Document
