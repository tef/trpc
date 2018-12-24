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
    if kind == 'Arguments':
        return Arguments(obj['values'])
    elif kind == 'Service':
        return Service(obj['name'],
            forms=obj['metadata']['forms'],
            links=obj['metadata']['links'],
            urls=obj['metadata']['urls'],
            embeds=obj['metadata']['embeds'],
        )
    else:
        return Response(obj)

def wrap(out):
    if not isinstance(out, Wire):
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

class Wire:
    fields = () # top level field names
    metadata = () # metadata field names
    apiVersion = 'v0'

    def __init__(self, **args):
        if self.kind != args['kind']:
            raise Exception('no')
        if self.apiVersion != args['apiVersion']:
            raise Exception('no')
        for k in zip(self.fields, self.metadata):
            setattr(self, k, args[k])

    @property
    def kind(self):
        return self.__class__.__name__


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
        return name in getattr(self, 'links', ())

    def has_form(self, name):
        return name in getattr(self, 'forms', ())

    def open_link(self, name, base_url):
        links = self.links
        if name not in self.links:
            raise Exception(name)

        url = self.urls.get(name, name)

        url = urljoin(base_url, url)

        cached = self.embeds.get(name)

        return Request('GET', url, None, cached)
    
    def submit_form(self, name, args, base_url):
        url = self.urls.get(name, name)
        url = urljoin(base_url, url)

        if name not in self.forms:
            if name in self.links:
                return Request('GET', url, None)
            raise Exception(name)

        arguments = {}
        form_args = self.forms[name]
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


class Response:
    def __init__(self, obj):
        self.kind = obj.pop('kind')
        self.apiVersion = obj.pop('apiVersion')
        self.metadata = obj.pop('metadata')
        self.fields = obj

    def __repr__(self):
        return self.kind

    def open_link(self, name, base_url):
        links = self.metadata['links']
        if name not in links:
            raise Exception(name)

        url = self.metadata['urls'].get(name, name)

        url = urljoin(base_url, url)

        cached = self.metadata.get('embeds',{}).get(name)

        return Request('GET', url, None, cached)

    def has_link(self, name):
        if 'links' in self.metadata:
            return name in self.metadata['links']

    def has_form(self, name):
        if 'forms' in self.metadata:
            return name in self.metadata['forms']

    def submit_form(self, name, args, base_url):
        links = self.metadata['links']
        forms = self.metadata['forms']
        if name not in forms:
            if name in links:
                url = self.metadata['urls'].get(name, name)
                url = urljoin(base_url, url)
                return Request('GET', url, None)
            raise Exception(name)

        url = self.metadata['urls'].get(name, name)
        url = urljoin(base_url, url)
        
        arguments = {}
        form_args = forms[name]
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


class Arguments(Wire):
    apiVersion = 'v0'
    fields = ('values',)
    metadata = ()

    def __init__(self,  values):
        self.values = values

class Result(Wire):
    apiVersion = 'v0'
    fields = ('value',)
    metadata = ()

    def __init__(self, value):
        self.value = value

class ResultSet(Wire):
    apiVersion = 'v0'
    fields = ('values',)
    metadata = ('next',)

    def __init__(self, value, next=None):
        self.value = value
        self.next = Next

class FutureResult(Wire):
    apiVersion = 'v0'
    fields = ()
    metadata = ('url', 'args', 'wait_seconds')

    def __init__(self, url, args, wait_seconds=120):
        self.url = url
        self.args = args
        self.wait_seconds = wait_seconds

class Procedure(Wire):
    apiVersion = 'v0'
    fields = ('name',)
    metadata = ('form')

    def __init__(self, name, form=()):
        self.name = name
        self.form = form

class Service(Wire):
    apiVersion = 'v0'
    fields = ('name',)
    metadata = ('links','forms', 'embeds', 'urls')

    def __init__(self, name, links, forms=(), embeds=(), urls=()):
        self.name = name
        self.links = links
        self.forms = forms or {}
        self.embeds = embeds or {}
        self.urls = urls or {}

class Namespace(Wire):
    apiVersion = 'v0'
    fields = ('name', )
    metadata = ('links','forms', 'embeds', 'urls')

    def __init__(self, name, links, forms=(), embeds=(), urls=()):
        self.name = name
        self.links = links
        self.forms = forms or {}
        self.embeds = embeds or {}
        self.urls = urls or {}

class Collection(Wire):
    apiVersion = 'v0'
    fields = ('name', )
    metadata = ('key','indexes', 'links','forms','embeds', 'urls')

    def __init__(self, name, key,  create, indexes, links=(), forms=(), embeds=(), urls=()):
        self.name = name
        self.key = key
        self.create = create
        self.indexes = indexes
        self.links = links
        self.forms = forms or {}
        self.embeds = embeds or {}
        self.urls = urls or {}

class Entry(Wire):
    apiVersion = 'v0'
    fields = ('name', )
    metadata = ('collection', 'links','forms', 'embeds', 'urls')

    def __init__(self, name, collection, links, forms=(), embeds=(), urls=()):
        self.name = name
        self.collection = collection
        self.links = links
        self.forms = forms or {}
        self.embeds = embeds or {}
        self.urls = urls or {}

class EntrySet(Wire):
    apiVersion = 'v0'
    fields = ('name', )
    metadata = ('collection',  'links','forms', 'embeds', 'urls')

    def __init__(self, name, collection, links, forms=(), embeds=(), urls=()):
        self.name = name
        self.collection = collection
        self.links = links
        self.forms = forms or {}
        self.embeds = embeds or {}
        self.urls = urls or {}

# Stream - one way

# Channel - two way

# Terminal - two way + result

# Document
