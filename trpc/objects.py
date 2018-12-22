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

def decode(data, content_type):
    if not data:
        return None
    if content_type == CONTENT_TYPE:
        return json.loads(data.decode('utf-8'))

def encode(out, accept):
    if not isinstance(out, Wire):
        out = Result(out)
    
    return out.encode(accept)

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

        url = self.metadata['urls'].get(name, name)

        url = urljoin(self.base_url, url)

        cached = self.metadata.get('embeds',{}).get(name)

        return Request('GET', url, None, cached)

    def has_link(self, name):
        if 'links' in self.metadata:
            return name in self.metadata['links']

    def has_form(self, name):
        if 'forms' in self.metadata:
            return name in self.metadata['forms']

    def submit_form(self, name, args):
        links = self.metadata['links']
        forms = self.metadata['forms']
        if name not in forms:
            if name in links:
                url = self.metadata['urls'].get(name, name)
                url = urljoin(self.base_url, url)
                return Request('GET', url, None)
            raise Exception(name)

        url = self.metadata['urls'].get(name, name)
        url = urljoin(self.base_url, url)
        
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
