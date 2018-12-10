from trpc import App, Service, rpc

class Example(Service):
    @rpc()
    def hello():
        return "world"

def nice(person):
    return False

namespace = {
    'Example': Example,
    'nice': nice,
}

app = App('example', namespace) # WSGI App

app.automain(__name__)


