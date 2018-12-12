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

class Wire:
    fields = () # top level field names
    metadata = () # metadata field names
    apiVersion = 'v0'

    @property
    def kind(self):
        return self.__class__.__name__


    def dump(self):
        fields = {k:getattr(self, k) for k in self.fields}
        metadata = {k:getattr(self, k) for k in self.metadata}
        return dict(
            kind=self.kind,
            apiVersion=self.apiVersion,
            metadata={} if not metadata else metadata,
            **fields
        )

    def encode(self, accept=None):
        data = json.dumps(self.dump())
        return CONTENT_TYPE, data.encode('utf-8')


class Request(Wire):
    apiVersion = 'v0'
    fields = ('arguments',)
    metadata = ()

    def __init__(self,  arguments):
        self.arguments = arguments


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
    metadata = ('url', 'wait_seconds')

    def __init__(self, url, wait_seconds=120):
        self.url = url
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
    metadata = ('key','indexes', 'fields', 'links','forms','embeds', 'urls')

    def __init__(self, name, key, indexes, fields, links=(), forms=(), embeds=(), urls=()):
        self.name = name
        self.key = key
        self.indexes = indexes
        self.fields = fields
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
