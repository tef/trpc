#!/usr/bin/env python3

"""
run ./example.py --port=1729 to run a server

or run ./example.py --schema to print the schema

or run ./example.py Example:hello to run a server, run a command over http, then stop the server
"""

from trpc.server import App, Future, Namespace, Service, rpc

class Example(Service):
    @rpc()
    def hello(self, name):
        return name

    def hello_future(self):
        return Future(self.hello, dict(name="from the future"))

namespace = {
    'Example': Example,
}

app = App('app', namespace) # WSGI App

app.automain(__name__)


