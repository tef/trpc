from trpc import App, Service, rpc

class Example(Service):
    @rpc()
    def hello():
        return "world"

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


