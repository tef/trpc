from trpc import App, Service, rpc

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

def nice(person):
    return False

def report():
    return [1,2,3]

namespace = {
    'Example': Example,
    'nice': nice,
    'nested': {
        'report': report,
    },
}

app = App('example', namespace) # WSGI App

app.automain(__name__)


