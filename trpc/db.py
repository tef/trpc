import types
import os, sys, uuid
from urllib.parse import urljoin, urlencode

from . import wire
from .server import App, ModelEndpoint, funcargs, rpc

from peewee import Database, Model
from playhouse.reflection import Introspector
from playhouse.db_url import connect as db_connect


class PeeweeEndpoint(ModelEndpoint):
    def __init__(self, app, prefix, name,  model):
        ModelEndpoint.__init__(self, app, prefix, name, model)

        self.pk = model._meta.primary_key
        self.key = self.pk.name
        self.fields = model._meta.fields
        self.create_fields = list(k for k,v in self.fields.items() if not v.primary_key)
        self.indexes = [self.key]
        self.indexes.extend(k for k,v in self.fields.items() if v.index or v.unique) 

    def describe_model(self):
        return wire.Model(
            name=self.name,
            key=self.key,
            create=self.create_fields,
            indexes=self.indexes,
            routes={}, urls={}, embeds={},
        )
    def describe_entry(self, obj):
        attrs = self.extract_attributes(obj)
        return wire.Entry(attributes=attrs)

    def get_entry(self, key):
        obj =  self.model.get(self.pk == key)
        return self.describe_entry(obj)

    def create_entry(self, data):
        obj = self.model.create(**data)
        return self.describe_entry(obj)

    def update_entry(self, key, data):
        pass

    def set_entry(self, key, data):
        pass

    def delete_entry(self, name):
        self.model.delete().where(self.pk == name).execute()

    def watch_entry(self, key): 
        pass

    def get_where(self, selector, state, limit):
        next = state
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

        items = [self.describe_entry(o).embed() for o in items]

        return wire.EntrySet(
            name=self.name, 
            selector={}, # dom.dump_selector(selector),
            items=items,
            next=next_token
        )

    def delete_where(self, selector):
        self.select_on(self.model.delete(), selector).execute()

    def watch_where(self, selector, cursor=None): 
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

if __name__ == '__main__':
    Model.make_trpc_endpoint=PeeweeEndpoint

    url = os.environ.get("DATABASE_URL","sqlite:///trpc.db")

    db = db_connect(url)
    db.connect()

    introspector = Introspector.from_database(db)
    endpoints = introspector.generate_models()
    database = introspector.introspect()


    app = App('Database', endpoints)
    app.main()


