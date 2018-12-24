"""
wire types:

all wire types are json objects and must have 'kind', 'apiVersion', 'metadata' fields

kind is built in or java style name
apiVersion is a string, without any ordering or semantic information defined.

metadata may contain
    'id', 'url' ,'collection'
    'links', 'methods', 'embeds'
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

class Request:
    def __init__(self, verb, url, data, cached):
        self.verb = verb
        self.url = url
        self.data = data
        self.cached = cached

class Message:
    Kinds = {}
    fields = () # top level field names
    metadata = () # metadata field names
    apiVersion = 'v0'

    # subclass hook
    def __init_subclass__(cls):
        cls.Kinds[cls.__name__] = cls

    # class methd ctor from obj
    @classmethod
    def init_from_dict(cls, obj):
        kind = obj.pop('kind')
        apiVersion = obj.pop('apiVersion')
        metadata = obj.pop('metadata')
        Kind = cls.Kinds.get(kind)
        if not Kind: return
        self = Kind.__new__(Kind)
        for name in Kind.fields:
            value = obj.get(name)
            setattr(self, name, value)
        for name in Kind.metadata:
            value = metadata.get(name)
            setattr(self, name, value)
        return self


    def __init__(self, *args, **kwargs):
        names = list()
        names.extend(self.fields)
        names.extend(self.metadata)
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
        fields = {k:getattr(self, k) for k in self.fields}
        return "{}: {}".format(self.kind, fields)

    def embed(self):
        fields = {k:getattr(self, k) for k in self.fields}
        metadata = {k:getattr(self, k) for k in self.metadata}
        return dict(
            kind=self.kind,
            apiVersion=self.apiVersion,
            metadata={} if not metadata else metadata,
            **fields
        )

    def encode(self, accept=None):
        data = json.dumps(self.embed())
        return CONTENT_TYPE, data.encode('utf-8')

    def has_link(self, name):
        return name in (getattr(self, 'links', ()) or ()) 

    def open_link(self, name, base_url):
        links = self.links
        if name not in self.links:
            raise Exception(name)

        url = self.urls.get(name, name)

        url = urljoin(base_url, url)

        cached = self.embeds.get(name)

        return Request('GET', url, None, cached)
    
class Arguments(Message):
    apiVersion = 'v0'
    fields = ('values',)
    metadata = ()


class Result(Message):
    apiVersion = 'v0'
    fields = ('value',)
    metadata = ()

    def format(self):
        return str(self.value)

class FutureResult(Message):
    apiVersion = 'v0'
    fields = ()
    metadata = ('url', 'args', 'wait_seconds')

    def make_request(self, base_url):
        url = urljoin(base_url, self.url)
        return Request('POST', url, self.args, None)

class Procedure(Message):
    apiVersion = 'v0'
    fields = ('arguments',)
    metadata = ()

    def call(self, args, base_url):
        url = base_url

        arguments = {}
        form_args = list(self.arguments)
        if form_args:
            while args:
                name, value = args.pop(0)
                if name is None:
                    name = form_args.pop(0)
                    arguments[name] = value
                else:
                    arguments[name] = value
                    form_args.remove(name)
        else:
            arguments = args

        return Request('POST', url, arguments, None)

class Service(Message):
    apiVersion = 'v0'
    fields = ('name',)
    metadata = ('links', 'embeds', 'urls')

class Namespace(Message):
    apiVersion = 'v0'
    fields = ('name', )
    metadata = ('links', 'embeds', 'urls')

class ResultSet(Message):
    apiVersion = 'v0'
    fields = ('values',)
    metadata = ('next',)

class Collection(Message):
    apiVersion = 'v0'
    fields = ('name', )
    metadata = ('key','create', 'indexes', 'links','embeds', 'urls')

class Entry(Message):
    apiVersion = 'v0'
    fields = ('name', )
    metadata = ('collection', 'links', 'embeds', 'urls')

class EntrySet(Message):
    apiVersion = 'v0'
    fields = ('rows', 'columns' )
    metadata = ('collection',  'links', 'embeds', 'urls')

# Stream - one way

# Channel - two way

# Terminal - two way + result

# Document
