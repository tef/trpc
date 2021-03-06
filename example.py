#!/usr/bin/env python3

"""
run ./example.py --port=1729 to run a server

or run ./example.py --schema to print the schema

or run ./example.py Example:hello to run a server, run a command over http, then stop the server
"""

from typing import List, Dict, Any

from trpc.server import App, Cursor, Future, Namespace, Service, rpc

class Example(Service):
    @rpc()
    def hello(self, name: str) -> str:
        return "Hello, {}!".format(name)

    @rpc()
    def sum(self, num: List[int]):
        return sum(num)

    @rpc()
    def hello_future(self):
        return Future(self.hello, dict(name="from the future"))

    @rpc()
    def hello_cursor(self):
        return Cursor(list(range(0,5)), self.hello_next, dict(n=5))

    @rpc()
    def hello_next(self, n):
        if n < 30:
            return Cursor(list(range(n, n+5)), self.hello_next, dict(n=n+5))
        else:
            return Cursor(list(range(n, n+5)), None, None)

    @rpc(raw_args=True)
    def echo(self, args):
        return args

namespace = {
    'Example': Example,
}

app = App('app', namespace) # WSGI App

app.automain(__name__)


