# trpc, yet another rpc library & toolkit

`trpc` is a python 3 framework for writing services, and comes with:

- a generic client api (no stubs!)
- a generic command line tool
- schema generation from code
- a generic server, for databases, too!

It uses JSON and HTTP underneath by default, but doesn't have to.

## Step 1: Define a service

```
from trpc import App, Service, rpc

def report():
    return [1,2,3]

namespace = {
    'report': report,
}

app = App('example', namespace) # WSGI App

app.automain(__name__) # If run as a script, run a HTTP server
```


## Step 2: Run the service

```
$ python example.py --port=1729
```

## Step 3: Interact with the service

```
$ trpc call report
[1,2,3]
```

Ok, you might need to install `trpc`, but `python -m trpc` works too. You'll also need to set the `TRPC_URL` environment variable.

## Step 4: Call the API

```
#!/usr/bin/env python3

import trpc
import sys

example = trpc.open(sys.argv[1])

print(example.report())
```

It uses `JSON` underneath, and supports sending/recieving strings, numbers, lists, and ordered maps (a hash/dictionary)

## A example service:

You can organize your RPC methods into namespaces and services.

```
class Example(Service):
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

```
$ trpc call nested:Example:hello sam
Hello, sam!
```

```
api = trpc.open("http://localhost:1729/")

print(api.Example.hello("Sam"))

```

# Where's the schema?

Although other frameworks use a schema to generate code, `trpc` works the other way around.

You can run `$ ./example.py --schema` to print the schema, or via code too:

```
app = App('name', root)
schema = app.schema()
json.dumps(schema.dump())
```

The schema is a json file, and describes the namespaces, services, and methods exposed.

# A model example

- _XXX_ 
    - Peewee handler to map a database table

```
$ trpc list Model --where-field=..
$ trpc get Model key
$ trpc delete Model key
```

# Instant service, just add database:

- _XXX_
    -  Using introspection, creating `Model`s at runtime

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

# Polling

- _XXX_
    - Similarly, API can tell client to poll for answer later
    - Handled in client code, command line tool
    - Can Change API to use it without changing clients

# Sessions

- _XXX_ 
    - Services with client side state attached
    - Useful for sharding an API

# Redirects

- _XXX_ 
 - Client follows URLs given by server, can redirect to other APIs

# How it works?

- _XXX_
    - it's restful, lol

# Authentication

Yes, that is nice.
