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
        return CONTENT_TYPE, json.dumps(dict(
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


