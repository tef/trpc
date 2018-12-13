import types

from urllib.parse import urljoin, urlencode

from . import objects
from .server import Endpoint, funcargs, rpc

class ModelEndpoint(Endpoint):
    def __init__(self, app, model):
        self.app = app
        self.model = model
        self.key = None
        self.create_fields = ()
        self.indexes = ()

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


    def describe_trpc_endpoint(self):
        return self.describe_collection()


    def create_entry(self, data): pass
    def get_entry(self, key): pass
    def update_entry(self, key, data): pass
    def set_entry(self, key, data): pass
    def delete_entry(self, key): pass
    def watch_entry(self, key): pass
    def call_entry(self, obj, method, args): pass

    def get_list(self, selector, cursor=None): pass
    def delete_list(self, selector): pass
    def set_list(self, selector, value): pass
    def update_list(self, selector, value): pass
    def watch_list(self, selector, cursor=None): pass


class PeeweeEndpoint(ModelEndpoint):
    def __init__(self, app, name,  model):
        self.app = app
        self.name = name
        self.pk = model._meta.primary_key
        self.key = self.pk.name
        self.fields = model._meta.fields
        self.create_fields = list(k for k,v in self.fields.items() if not v.primary_key)
        self.indexes = [self.key]
        self.indexes.extend(k for k,v in self.fields.items() if v.index or v.unique) 
        self.model = model

    def describe_collection(self):
        methods = {}
        urls = {}
        return objects.Collection(
            name=self.name,
            key=self.key,
            create=self.create_fields,
            indexes=self.indexes,
            links=(), forms=methods, urls=urls,
        )

    def describe_entry(self, name, key,  entry):
        pass

    def create_entry(self, data):
        return self.model.create(**data)

    def get_entry(self, key):
        return self.model.get(self.pk == name)

    def update_entry(self, key, data):
        pass

    def set_entry(self, key, data):
        pass

    def delete_entry(self, name):
        self.model.delete().where(self.pk == name).execute()

    def watch_entry(self, key): 
        pass

    def get_list(self, selector, state):
        limit, next = state
        items = self.model.select()
        pk = self.pk
        next_token = None
        if selector:
            items = self.select_on(items, selector)

        if limit or next:
            items = items.order_by(pk)
            if next:
                items = items.where(pk > next)
            if limit:
                items = items.limit(limit)

            items = list(items)
            if items:
                next_token = self.key_for(items[-1])
        else:
            items = list(items)

        return objects.EntrySet(
            name=self.name, 
            selector=dom.dump_selector(selector),
            items=items,
            next=next_token
        )

    def delete_list(self, selector):
        self.select_on(self.model.delete(), selector).execute()

    def set_list(self, selector, value):
        pass
    def update_list(self, selector, value): 
        pass

    def watch_list(self, selector, cursor=None): 
        pass

    def extract_attributes(self, obj):
        attr = dict()
        for name in self.fields:
            a = getattr(obj, name)
            if isinstance(a, uuid.UUID):
                a = a.hex
            attr[name] = a
        return attr

    def key_for(self, obj):
        name = self.pk.name
        attr = getattr(obj, name)
        if isinstance(attr, uuid.UUID):
            attr = attr.hex
        return attr

    def select_on(self, items, selector):
        for s in selector:
            key, operator, values = s.key, s.__class__, s.value
            field = self.fields[key]
            if operator == dom.Operator.Equals:
                items = items.where(field == values)
            elif operator == dom.Operator.NotEquals:
                items = items.where(field != values)
            else:
                raise Exception('unsupported')
        return items



