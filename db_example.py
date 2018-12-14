#!/usr/bin/env python3

import uuid

from peewee import SqliteDatabase, Model, UUIDField, CharField

from trpc import server, db as trpc_db

Model.make_trpc_endpoint = trpc_db.PeeweeEndpoint

db = SqliteDatabase('people.db')

class Person(Model):
    class Meta: database = db

    uuid = UUIDField(primary_key=True, default=uuid.uuid4)
    name = CharField(index=True)
    job = CharField(index=True)

    @server.rpc()
    def hello(self):
        return "Hello, {}!".format(self.name)


db.connect()
db.create_tables([Person], safe=True)

namespace = {'Person': Person }

app = server.App('db', namespace)

app.automain(__name__)
