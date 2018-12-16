#!/usr/bin/env python3

"""
run ./example.py --port=1729 to run a server

or run ./example.py --schema to print the schema

or run ./example.py Example:hello to run a server, run a command over http, then stop the server
"""

from trpc import App, Service, rpc, Namespace

class Example(Service):
    @rpc()
    def hello(self):
        return "world"

    def echo(self, **args):
        return {
            "prefix": self.route.prefix,
            "head": self.route.head,
            "args": args,
        }

class Two(Namespace):
    class Example(Service):
        def hello(self):
            return "two"

def nice(person):
    return False

def report():
    return [1,2,3]

namespace = {
    'Example': Example,
    'nice': nice,
    'two': Two,
    'nested': {
        'report': report,
    },
}

app = App('example', namespace) # WSGI App

app.automain(__name__)


