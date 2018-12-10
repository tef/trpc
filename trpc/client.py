import types
import socket
import traceback
import urllib.request
import sys
import os
import json
import shlex
import threading
import inspect

from . import objects

from urllib.parse import urljoin, urlencode, parse_qsl
from wsgiref.simple_server import make_server, WSGIRequestHandler

CONTENT_TYPE = objects.CONTENT_TYPE

class Client:
    def __init__(self):
        pass

    class Request:
        def __init__(self, verb, url, data):
            self.verb = verb
            self.url = url
            self.data = data
        
    class Response:
        def __init__(self, base_url, kind, apiVersion, metadata, fields):
            self.base_url = base_url
            self.kind = kind
            self.apiVersion = apiVersion
            self.metadata = metadata
            self.fields = fields


        def __repr__(self):
            return self.kind

        def open_link(self, name):
            links = self.metadata['links']
            if name not in links:
                raise Exception(name)

            url = urljoin(self.base_url, name) + "/"

            return Client.Request('GET', url, None)

        def submit_form(self, name, args):
            links = self.metadata['links']
            forms = self.metadata['forms']
            if name not in forms:
                if name in links:
                    url = urljoin(self.base_url, name)
                    return Client.Request('GET', url, None)
                raise Exception(name)

            url = urljoin(self.base_url, name)
            return Client.Request('POST', url, args)

    def fetch(self, request):
        if isinstance(request, str):
            request = self.Request("GET", request, None)

        data = request.data
        if data is None:
            data = ""
        else:
            content_type, data = objects.Request(data).encode()

        data = data.encode('utf8')

        urllib_request= urllib.request.Request(
            url=request.url,
            data=data,
            method=request.verb,
            headers={'Content-Type': CONTENT_TYPE},
        )

        with urllib.request.urlopen(urllib_request) as fh:
            base_url = fh.url
            obj = json.load(fh)

        kind = obj.pop('kind')
        if kind == 'Response':
            return obj['value']
        apiVersion = obj.pop('apiVersion')
        metadata = obj.pop('metadata')

        return self.Response(base_url, kind, apiVersion, metadata, obj)


class Remote:
    def __init__(self, client, response):
        self.client = client
        self.obj = response

    def __getattr__(self, name):
        if name in self.obj.metadata.get('links',()):
            req = self.obj.open_link(name)
            obj = self.client.fetch(req)
            if isinstance(obj, self.client.Response):
                return Remote(self.client, obj)
            return obj
        if name in self.obj.metadata.get('forms',()):
            def method(**args):
                req = self.obj.submit_form(name, args)
                obj = self.client.fetch(req)
                if isinstance(obj, self.client.Response):
                    return Remote(self.client, obj)
                return obj
            return method
        raise Exception('no')

def open(endpoint):
    c = Client()
    obj = c.fetch(endpoint)
    return Remote(c, obj)

    
