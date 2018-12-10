from trpc import App, Model, Service

class Example(Service):
    @rpc()
    def hello():
        return "world"

namespace = {
    'Example': Example
}

app = App(namespace)

app.automain(__name__)


