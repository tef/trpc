import urllib.request
import sys
import os
import json

from urllib.parse import urljoin, urlencode

from . import objects

class Session:
    def __init__(self):
        pass

    class APIRequest:
        def __init__(self, verb, url, data):
            self.verb = verb
            self.url = url
            self.data = data
        
    class APIResponse:
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

            url = urljoin(self.base_url, name) # + "/"

            return Session.APIRequest('GET', url, None)

        def has_link(self, name):
            if 'links' in self.metadata:
                return name in self.metadata['links']

        def has_form(self, name):
            if 'forms' in self.metadata:
                return name in self.metadata['forms']

        def submit_form(self, name, args):
            links = self.metadata['links']
            forms = self.metadata['forms']
            if name not in forms:
                if name in links:
                    url = urljoin(self.base_url, name)
                    return Session.APIRequest('GET', url, None)
                raise Exception(name)

            url = urljoin(self.base_url, name)
            return Session.APIRequest('POST', url, args)

    def fetch(self, request):
        if isinstance(request, str):
            request = self.APIRequest("GET", request, None)

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
            headers={'Content-Type': objects.CONTENT_TYPE},
        )

        with urllib.request.urlopen(urllib_request) as fh:
            base_url = fh.url
            obj = json.load(fh)

        kind = obj.pop('kind')
        apiVersion = obj.pop('apiVersion')
        metadata = obj.pop('metadata')

        return self.APIResponse(base_url, kind, apiVersion, metadata, obj)


class Client:
    def __init__(self, session, response):
        self.session = session
        self.obj = response

    def unwrap(self, obj):
        if isinstance(obj, self.session.APIResponse):
            if obj.kind == 'Response':
                return obj.fields['value']
            return Client(self.session, obj)
        return obj

    def __getattr__(self, name):
        if name in self.obj.metadata.get('links',()):
            req = self.obj.open_link(name)
            obj = self.session.fetch(req)
            return self.unwrap(obj)
        if name in self.obj.metadata.get('forms',()):
            def method(**args):
                req = self.obj.submit_form(name, args)
                obj = self.session.fetch(req)
                return self.unwrap(obj)
            return method
        raise Exception('no')

def open(endpoint):
    session = Session()
    obj = session.fetch(endpoint)
    return Client(session, obj)

    
