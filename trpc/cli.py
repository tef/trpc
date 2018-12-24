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

        mode, path, args = self.parse(argv, environ)
        self.run(mode, path, args, environ)

    def complete(self, prefix):
        pass

    def run(self, mode, path, args, environ):
        endpoint = environ.get("TRPC_URL", "")

        if not endpoint:
            print("Set TRPC_URL first", file=sys.stderr)
            sys.exit(-1)

        url, obj = self.session.request(endpoint)

        for p in path:
            url, obj = self.session.request(obj.open_link(p, url))

        if obj.kind == "Procedure" and mode == None:
            mode = "call"
    
        if mode == 'call':
            req = obj.call(args, url)
            url, obj = self.session.request(req) 

        print(obj.format())

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
                args.append((name, value))
            else:
                name, value = None, arg
                args.append((name, value))
        return mode, path, args


    
