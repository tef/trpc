from trpc import App, Service, rpc

class Example(Service):
    @rpc()
    def hello():
        return "world"

@rpc()
def lie():
    return "everything is fine"

namespace = {
    'Example': Example,
    'lie': lie,
}

app = App(namespace) # WSGI App

app.automain(__name__)


