from trpc import App, Service, rpc

class Example(Service):
    @rpc()
    def hello():
        return "world"

namespace = {
    'Example': Example,
}

app = App('example', namespace) # WSGI App

app.automain(__name__)


