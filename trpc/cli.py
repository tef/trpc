import traceback
import sys
import os
import shlex

class CLI:
    MODES = set((
        'call', 'get', 'list',
        'set', 'update', 'create'
        'delete',   
        'watch', 'exec'
        'help', 'error', 'usage', 'complete', 'version'
    ))

    def __init__(self, session):
        self.session = session

    def main(self, argv, environ):
        if 'COMP_LINE' in environ and 'COMP_POINT' in environ:
            # Bash Line Completion.
            line, offset =  environ['COMP_LINE'], int(environ['COMP_POINT'])
            try:
                prefix = shlex.split(line[:offset])
                # if there's mismatched ''s bail
            except ValueError:
                sys.exit(0)

            prefix = line[:offset].split(' ')
            for o in self.complete(prefix):
                print(o)
            sys.exit(0)

        self.run(argv, environ)

    def complete(self, prefix):
        pass

    def run(self, argv, environ):
        endpoint = environ.get("TRPC_URL", "")

        if not endpoint:
            print("Set TRPC_URL first", file=sys.stderr)
            sys.exit(-1)

        mode, path, args = self.parse(argv, environ)

        obj = self.session.fetch(endpoint)

        for p in path[:-1]:
            obj = self.session.fetch(obj.open_link(p))
    
        if path:
            name = path[-1]
            if mode == None or mode == 'call':
                if obj.has_link(name) and not args:
                    req = obj.open_link(path[-1])
                elif obj.has_form(name):
                    req = obj.submit_form(path[-1], dict(args))
                else:
                    raise Exception(name)
                obj = self.session.fetch(req) 
        if obj.kind == 'Object':
            print(obj.fields['value'])
        else:
            print(obj.kind)
            for link in obj.metadata.get('links', ()):
                print(link)
            for form in obj.metadata.get('forms', ()):
                print(form)
        return

    def parse(self, argv, environ):
        mode = None
        if argv and argv[0] in self.MODES:
            mode = argv.pop(0)

        path = ""
        app_args = []
        args = []
        
        if argv and not argv[0].startswith('--'):
            path = argv.pop(0).split(':')

        flags = True
        for arg in argv:
            name, value = None, None
            if flags and arg == '--':
                flags = False
                continue
            if flags and arg.startswith('--'):
                if '=' in arg:
                    name, value = arg[2:].split('=', 1)
                else:
                    name, value = arg[2:], None
            else:
                name, value = None, arg
            args.append((name, value))
        return mode, path, args


    
