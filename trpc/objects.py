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
        out = Object(out)
    
    return out.encode()

class Wire:
    fields = () # top level field names
    metadata = () # metadata field names
    apiVersion = 'v0'

    @property
    def kind(self):
        return self.__class__.__name__


    def encode(self, accept=None):
        fields = {k:getattr(self, k) for k in self.fields}
        metadata = {k:getattr(self, k) for k in self.metadata}
        data = json.dumps(dict(
            kind=self.kind,
            apiVersion=self.apiVersion,
            metadata={} if not metadata else metadata,
            **fields
        ))

        return CONTENT_TYPE, data.encode('utf-8')



class Request(Wire):
    apiVersion = 'v0'
    fields = ('arguments',)
    metadata = ()

    def __init__(self, arguments):
        self.arguments = arguments

class Object(Wire):
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


