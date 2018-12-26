import traceback
import subprocess
import sys
import os
import shlex
import shutil
import unicodedata
import contextlib
import os.path
import json

from datetime import datetime, timezone

# Errors

class Bug(SyntaxError): pass # Bad Code
class Error(Exception): pass # Bad Input

# Wrappers for shell programs: less, $EDITOR, and git

@contextlib.contextmanager
def PAGER(use_less=True):
    if use_less and sys.stdout.isatty() and sys.stderr.isatty():
        env = {}
        env.update(os.environ)
        env["LESS"] = "FRX"
        env["LV"] = "-c"
        p = subprocess.Popen(
            'less',
            env=env, 
            stdin=subprocess.PIPE,
            encoding='utf8'
        )
        width, height = shutil.get_terminal_size((None, None))
        try:
            yield p.stdin, width
        finally:
            p.stdin.close()
            while p.poll() is None:
                try:
                    p.wait()
                except KeyboardInterrupt:
                    pass
    else:
        yield sys.stdout, None

class ArgumentParser:
    """
        p = ArgumentParser({ first="--str?", second="--str*", third="str+", })

        running:
            p.parse("--first=a --second=b --second=b 1 2 3 4")

        gives
            {
                "first": "a", 
                "second": ["b", "c"],
                "third": ["1", "2", "3", "4"]
            }

        arguments can be named, '--kind', or positional 'kind'
        only one argument can be positional

        kinds are:

            string, str
            int, integer
            float, num, number
            path, file, dir

        kinds can be annotated:

                --kind   exactly 1 of named arg
                           no default
                --kind?  0 or 1 of named arg
                           default None
                --kind*  0 or more of named arg
                           default ()
                --kind+  1 or more of named arg
                           no default

                kind       1 of, positional
                           no default
                kind?     0 or 1 of, positional
                           default None
                kind*  0 or more of tail
                           default ()
                kind+    1 or more of tail
                           no default
    """
        
    KINDS = set((
        'str', 'string', 'json', 'json_or_scalar',
        'bool', 'boolean', 
        'int', 'integer',
        'num', 'number', 'float',
        'path', 'file', 'dir',
    ))

    def __init__(self, expected):
        """
            expected is a dict of name:kind
            kind is str, int, bool, etc
        """
        argspec = {}
        positional = None
        flags = False
        for name, value in expected.items():
            if positional:
                raise Bug("Commands can only take one type of positional arg")
            elif value.startswith("--"):
                flags = True
                if value.endswith("?"):
                    argspec[name] = ("named?", value[2:-1])  
                elif value.endswith("*"):
                    argspec[name] = ("named*", value[2:-1])  
                elif value.endswith("+"):
                    argspec[name] = ("named+", value[2:-1])  
                else:
                    argspec[name] = ("named", value[2:])  
            elif value.endswith('?'):
                positional = name
                argspec[name] = ("positional?", value[:-1])  
            elif value.endswith('*'):
                positional = name
                argspec[name] = ("positional*", value[:-1])  
            elif value.endswith('+'):
                positional = name
                argspec[name] = ("positional+", value[:-1])  
            else:
                positional = name
                argspec[name] = ("positional", value) 
        for key, value in argspec.items():
            rule, kind = value
            if kind not in self.KINDS:
                raise Bug('bad kind: {!r}'.format(kind))
            elif kind == "bool" and rule.startswith('positional'):
                raise Bug('why a positional bool? no')
        self.argspec = argspec
        self.positional = positional
        self.flags = flags

    def parse(self, args, named_args=False, defaults=True):
        """ args is a list of (name, value) pairs """
        argspec, flags, positional = self.argspec, self.flags, self.positional
        fn_args = {}
        for name, value in args:
            if name is None:
                if named_args:
                    raise Error("Can't mix positional argument and also pass it as a named argument")
                name = positional
                if name is None:
                    raise Error("Unexpected argument: {}".format(value))
                rule, kind = argspec[name]
                if rule in ('positional+', 'positional*'):
                    if name not in fn_args: fn_args[name] = []
                    fn_args[name].append(parse_argument(kind, value))
                else:
                    fn_args[name] = parse_argument(kind, value)
            elif name not in argspec:
                raise Error('unknown arg: --{}'.format(name))
            else:
                rule, kind = argspec[name]
                if kind == 'bool' and value is None:
                    value = True
                else:
                    value = parse_argument(kind, value)
                if rule in ('named+', 'named*', 'positional*', 'positional+'):
                    if name not in fn_args: fn_args[name] = []
                    fn_args[name].append(value)
                elif name in fn_args:
                    raise Error('duplicate argument --{}'.format(name))
                else:
                    fn_args[name] = value
                if rule.startswith("positional"):
                    named_args = True
        missing = []
        for name, value in argspec.items():
            rule, kind = value
            if name in fn_args:
                continue
            if rule in ('named?', 'positional?'):
                if defaults: fn_args[name] = None
            elif rule in ('named*', 'positional*'):
                if defaults: fn_args[name] = ()
            else:
                missing.append((name, rule, kind))

        if missing:
            out = []
            for name, rule, kind in missing:
                if rule.startswith('named'):
                    out.append('--{}=<{}>'.format(name, kind))
                elif rule.startswith('positional'):
                    out.append('<{}>'.format(kind))
            raise Error("missing arguments: {}".format(" ".join(out)))
        return fn_args

    def complete_named(self, args):
        arg = args[-1]

        if arg.startswith('--') and '=' in arg:
            name, value = arg[2:].split('=',1)
            if name in self.argspec:
                rule, kind = self.argspec[name]
                return self.complete_kind(kind, value)
            else:
                return ()
        out = []
        if arg.startswith('--') and '--' not in args[:-1]:
            argname = arg[2:]
            for name, value in self.argspec.items():
                rule, kind = value
                if name.startswith(argname):
                    if not argname and name in ('version','debug', 'help',):
                        continue # HACK
                    if rule.startswith('named') and kind == 'bool':
                        out.append('--{} '.format(name))
                    else:
                        out.append('--{}='.format(name))


        return out

    def complete(self, args, app_parser):
        arg = args[-1]

        if arg.startswith('--') and '=' in arg:
            name, value = arg[2:].split('=',1)
            if name in self.argspec:
                rule, kind = self.argspec[name]
                return self.complete_kind(kind, value)
            elif app_parser:
                return app_parser.complete_named(args)
            else:
                return ()

        out = []
        if app_parser:
            out.extend(app_parser.complete_named(args))
        if (not arg or arg.startswith('-')) and '--' not in args[:-1]:
            if not arg:
                out.append('')
            if arg in ('', '-', '--'):
                out.append('-- ')
            argname = arg[2:]
            for name, value in self.argspec.items():
                rule, kind = value
                if name.startswith(argname):
                    if rule.startswith('named') and kind == 'bool':
                        out.append('--{} '.format(name))
                    else:
                        out.append('--{}='.format(name))

        if (not arg) or (not arg.startswith('-') or '--' in args[:-1]):
            if self.positional:
                rule, kind = self.argspec[self.positional]
                out.extend(self.complete_kind(kind, arg))

        return out

    def complete_kind(self, kind, value):
        out = []
        if kind in ('path', 'dir', 'file'):
            if value:
                out.extend("{} ".format(p) for p in os.listdir() if p.startswith(value))
            else:
                out.extend("{} ".format(p) for p in os.listdir() if not p.startswith('.'))
        elif kind in ('bool', 'boolean'):
            vals = ('true ','false ')
            if value:
                out.extend(p for p in vals if p.startswith(value))
            else:
                out.extend(vals)
        return out

def parse_argument(kind, value):
    print(value)
    if kind in (None, "str", "string"):
        return value
    elif kind in ("path", "file", "dir"):
        return os.path.normpath(os.path.join(os.getcwd(), value))
    elif kind in ("int","integer"):
        try:
            return int(value)
        except ValueError:
            raise Error('got {} expecting integer'.format(value))
    elif kind in ("float","num", "number"):
        try:
            return float(value)
        except ValueError:
            raise Error('got {} expecting float'.format(value))
    elif kind in ("bool", "boolean"):
        try:
            return {'true':True, 'false':False, None: True}[value]
        except KeyError:
            raise Error('expecting true/false, got {}'.format(value))
    elif kind == "json":
        try:
            return json.loads(value)
        except ValueError:
            raise Error('got {} expecting json'.format(value))
    elif kind == "json_or_scalar":
        try: return int(value)
        except: pass
        try: return float(value)
        except: pass
        try: return json.loads(value)
        except: raise # pass
        return value
    return value


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

        url, obj = self.session.request(endpoint, None)

        for p in path:
            url, obj = self.session.request(obj.get(p), url)

        if obj.kind == "Procedure" and mode == None:
            mode = "call"
    
        if mode == 'call':
            if obj.command_line:
                a = ArgumentParser(obj.command_line)
                arguments = a.parse(args)
            elif obj.arguments is not None:
                arguments = {}
                form_args = list(obj.arguments)
                while args:
                    name, value = args.pop(0)
                    if name is None:
                        name = form_args.pop(0)
                        arguments[name] = value
                    else:
                        arguments[name] = value
                        form_args.remove(name)
            else:
                arguments = {}
                for k,v in args:
                    if k is None: raise Exception('no')
                    print(k,v)
                    arguments[k] = parse_argument('json_or_scalar', v)

            req = obj.call(arguments)
            url, obj = self.session.request(req, url) 

        with PAGER() as (stdout, width):
            if obj.kind == 'ResultSet':
                while obj != None:
                    for value in obj.values:
                        print(value, file=stdout)
                    req = obj.request_next()
                    if req:
                        url, obj = self.session.request(req, url)
                    else:
                        obj = None

            else:
                print(obj.format(), file=stdout)

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


    
