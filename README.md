# trpc

trpc is a toolkit for writing and interacting with client-server APIs.

trpc is also a command line tool: you don't need to implement a client, or a server, to use it.

trpc is also a framework: you can mix and match rpc and crud, break up large or long responses without breaing clients, and y can even generate the schema from the code, too!

trpc is also restful rpc framework, but that's not important and no-one cares

This is a proof of concept library, so forgive me again for implementing before documenting. Every example works, except where noted.

# You don't have to write server code

If you have a database lying around, you can turn it into a trpc service from the command line

```
$ export DATABASE_URL=sqlite:///example.db
$ python3 -m trpc.db:server

http://127.0.0.1:1729/
Press ^C to exit
```

# You don't have to write client code

`trpc` comes with a command line tool for interacting with any trpc server:

Setup:

```
$ export TRPC_URL=http://127.0.0.1:1729/
$ alias trpc='python3 -m trpc'
$ complete -o nospace -C trpc trpc
```

Use:

```
$ trpc list TableName
$ trpc create Table --field=1 --otherfield=3
$ trpc call stored_proc --arg=1 # (this bit does not work yet)
```

Tab complete works, too!

# You can write client code if you'd like to

```
import trpc

db = trpc.open("http://127.0.0.1:1729")

db.Table.create(key="1", value="v")

for row in db.Table.list():
    print(row.key, row.value)
```

# You can write custom servers, too

```
from trpc.server import App, Service, rpc

class Demo(Service):
    @rpc()
    def hello(self, name: str):
        return "Hello, {}!".format(name)

namespace = {'demo': demo}

app = trpc.App('example', namespace) # WSGI App

app.automain(__name__) # If run as a script, run a HTTP server
```

Running this with `$ ./example.py --serve --port=1729` gives you an HTTP server

# You don't need to write a new cli tool

The cli tool only needs the URL:

```
$ export TRPC_URL=...
$ trpc demo:hello --name="Sam"
Hello, Sam!
```

# Or generate new client stubs

The python client library only needs the URL, too.

```
import trpc

example = trpc.open("http://127.0.0.1:1729")

out = example.demo.hello("Sam")

print(out)
```

# You don't need to write a schema, either

The server can make one for you:

```
$ ./example_server.py --schema
```

Or you can make one yourself

```
app = App('name', root)
schema = app.schema()
json.dumps(schema.dump())
```

# Did I mention tab complete still works?

```
$ trpc demo:<TAB>
hello
```

# You can mix and match CRUD and Procedural

```
import uuid

from trpc.service import Service, App, rpc
from trpc.db import PeeweeEndpoint

from peewee import SqliteDatabase, Model, UUIDField, CharField

db = SqliteDatabase('people.db')

class Person(Model):
    make_trpc_endpoint = PeeweeEndpoint
    class Meta: database = db

    uuid = UUIDField(primary_key=True, default=uuid.uuid4)
    name = CharField(index=True)
    job = CharField(index=True)


class Demo(Service):
    @rpc()
    def hello(self, name: str):
        return "Hello, {}!".format(name)


db.connect()
db.create_tables([Person], safe=True)

namespace = {'Person': Person, 'demo':Demo}

app = App('db', namespace)

app.automain(__name__)
```

```
$ trpc call demo:hello --name=Sam
$ trpc create Person --name=Sam
```

# You can break up long running RPC calls without changing the client

Consider a service:

```
class Resizer(Service):
    @rpc()
    def resize(self, src, dest, size):
        data = store.load(src)
        imagetool.load(data)
        imagetool.resize(size)
        data = imagetool.save()
        store.save(dest, data)
```

At some point the operation might take so long that the HTTP call starts timing out.

The traditional fix is to break the operation into two parts:

```
class Resizer(Service):
    @rpc()
    def start_resize(self, src, dest, size):
        ...
        return resize_id
    @rpc()
    def resize_complete(self, resize_id):
        ...
```

With trpc, you can return a Future

```
from trpc.server import App, Service, Future, rpc

class Resizer(Service):
    @rpc()
    def resize(self, src, dest, size):
        ...
        return Future(self.resize_complete, {"resize_id":resize_id})
    @rpc()
    def resize_complete(self, resize_id):
        ...
        if ready:
            ...
        else:
            return Future(self.resize_complete, {"resize_id":resize_id})
```

To the client, or the CLI tool, `Resizer.resize()` works the same as before:

```
$ trpc call Resizer:resize --src=... --dest=... --size=...
```

```
api = trpc.open(...)
if api.Resizer.resize(....):
    ...
```

# You can break up large responses too!

From:

```
class Example(Service):
    @rpc()
    def make_list(self):
        return list(range(0,30))
```

To:

```
from trpc.server import App, Cursor, Future, Namespace, Service, rpc

class Example(Service):
    @rpc()
    def make_list(self):
        values = list(range(0,5))
        args = {"n":5}
        return Cursor(values, self.next_list, args)

    @rpc()
    def next_list(self, n):
        values = list(range(n,n+5))
        if n < 30:
            args = {"n":5}
            return Cursor(values, self.next_list, args)
        else:
            return Cursor(values, None, None)
```

Again, this is transparent to the client and the CLI. Both make multiple requests behind the scenes.

# How does it work?

The command line tool either has to know in advance how every api works, or, learn the schema somehow when interacting with the service. `trpc` chooses the latter approach. This, along with other decisions allows a `trpc` service to change behaviours without breaking clients.

You can add a new service, or a new method, without forcing the client libraries to change. The client knows about different types of api responses too, including ones requiring polling. A busy or hot method can be replaced with one that forces clients to poll for an answer, and control the polling interval too, without changing or updating clients, or breaking them too!

Although other frameworks use a schema to generate code, `trpc` works the other way around.

The schema is a json file, and describes the namespaces, services, and methods exposed. There's room for types, too. You can generate server templates, or client stubs from schemas, but you don't need to. `trpc` works without it. If you want to check a service matches up, add a test to your CI to dump the schema & compare it.

Although `trpc` uses JSON and HTTP underneath by default, but doesn't have to. Although `trpc` is written in python, there is nothing python specific about the `trpc` protocol or encodings.

# Readme TODO

- fill out examples
- explain rest/state transfer/uniform representation, uniform address, and self descriptive messaging
