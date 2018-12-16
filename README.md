# trpc: yet another rpc toolkit

Please note: This readme is optimistic and describes a finished product. Parts are missing.

`trpc` is an rpc framework that works differently from most others

1. you can generate the schema from the code
2. but the client doesn't need the schema
3. there's a reusable command line tool
4. and a reusable server, too!

With `trpc`, you can turn any database into an api server.

```
$ export DATABASE_URL=sqlite:///example.db
$ python3 -m trpc.db:server

http://127.0.0.1:1729/
Press ^C to exit
```

Then you can access it from the command line, using only the URL!

```
$ export TRPC_URL=http://127.0.0.1:1729/
$ alias trpc='python3 -m trpc'
$ python3 trpc list TableName
...

$ python3 -m trpc create Person --name='bob'
...
```

Or you can use the API directly:

```
import trpc

api = trpc.open('http://localhost:1729')

for row in api.Person.list():
    print(row.name)
```

It also comes with a Python 3 library for writing your own services:

```
import trpc

def demo():
    return "Hello, World!"

namespace = {'demo': demo}

app = trpc.App('example', namespace) # WSGI App

app.automain(__name__) # If run as a script, run a HTTP server
```

Run it with `python3 example.py --port=1729`, and then you can access it from the command line:

```
$ trpc demo
Hello, World!
```

Or you can call the API directly:

```
api = trpc.open('http://localhost:1729')
print(api.demo())
```

You don't need to know the names of the commands, either

```
$ trpc demo
usage: trpc demo --name=<...>
```

There's even tab completion (or will be!)

Although `trpc` uses JSON and HTTP underneath by default, but doesn't have to. Although `trpc` is written in python, there is nothing python specific about the `trpc` protocol or encodings.

# Where's the schema?

Although other frameworks use a schema to generate code, `trpc` works the other way around.

You can run `$ ./example.py --schema` to print the schema, or via code too:

```
app = App('name', root)
schema = app.schema()
json.dumps(schema.dump())
```

The schema is a json file, and describes the namespaces, services, and methods exposed. There's room for types, too. You can generate server templates, or client stubs from schemas, but you don't need to. `trpc` works without it.

If you want to check a service matches up, add a test to your CI to dump the schema & compare it.

# Why, in all that is good, would you do that?

The command line tool either has to know in advance how every api works, or, learn the schema somehow when interacting with the service. `trpc` chooses the latter approach. This, along with other decisions allows a `trpc` service to change behaviours without breaking clients.

You can add a new service, or a new method, without forcing the client libraries to change. The client knows about different types of api responses too, including ones requiring polling. A busy or hot method can be replaced with one that forces clients to poll for an answer, and control the polling interval too, without changing or updating clients, or breaking them too!

Take an example service:

```
class Example(trpc.Service):
    def hello(self, name):
        return "Hello, {}!".format(name)

namespace = {
    ...
    'nested': {
        'Example':'example'
    },
    ...
}
```

You can can call it from the command line:

```
$ trpc call nested:Example:hello --name=sam
Hello, sam!
```

Or, call it directly:

```
api = trpc.open("http://localhost:1729/")

print(api.Example.hello("Sam"))

```

- _XXX_
    - Similarly, API can tell client to poll for answer later
    - Handled in client code, command line tool
    - Can Change API to use it without changing clients

# A model example

- _XXX_ 
    - Peewee handler to map a database table

```
$ trpc list Model --where-field=..
$ trpc get Model key
$ trpc delete Model key
```

# Pagination 

- _XXX_
    - Servers can expose Cursors
    - State stored client side, but generically, invisibly
    - Break a long response into smaller API requests 

```
for row in endpoint.Model.all():
    print(row)
```

```
$ trpc list Model 
```

# Sessions

- _XXX_ 
    - Services with client side state attached
    - Useful for sharding an API

# Redirects

- _XXX_ 
 - Client follows URLs given by server, can redirect to other APIs

# asyncio

- _XXX_
    - alternate client api

# Alternate transports, encodings, clients, services

- _XXX_
    - decorating methods to indicate type
    - grpc decorator
    - ssh+trpc://

# How it works?

- _XXX_
    - it's restful, lol

# Authentication

Yes, that is nice, and would be nice to have. 
