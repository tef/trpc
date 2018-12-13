import urllib.request
import sys
import os
import json

from urllib.parse import urljoin, urlencode

from . import objects

class APIRequest:
    def __init__(self, verb, url, data, cached):
        self.verb = verb
        self.url = url
        self.data = data
        self.cached = cached
    
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

        url = self.metadata['urls'].get(name, name)

        url = urljoin(self.base_url, url)

        cached = self.metadata.get('embeds',{}).get(name)

        return APIRequest('GET', url, None, cached)

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
                url = self.metadata['urls'].get(name, name)
                url = urljoin(self.base_url, url)
                return APIRequest('GET', url, None)
            raise Exception(name)

        url = self.metadata['urls'].get(name, name)
        url = urljoin(self.base_url, url)
        
        arguments = {}
        form_args = forms[name]
        if form_args:
            while args:
                name, value = args.pop(0)
                if name is None:
                    name = form_args.pop(0)
                    arguments[name] = value
                else:
                    arguments[name] = value
                    form_args.remove(name)
        else:
            arguments = args

        return APIRequest('POST', url, arguments, None)

    def wrap(self, session):
        if self.kind == 'Result':
            return self.fields['value']
        elif self.kind == 'Namespace':
            return Namespace(self, session)
        elif self.kind == 'Service':
            return Service(self, session)
        elif self.kind == 'Collection':
            return Collection(self, session)
        else:
            return self

class APIClient:
    pass

class Navigable(APIClient):
    def __init__(self, response, session=None):
        self._response = response
        self._session = session

    def _fetch(self, req):
        if self._session:
            response = self._session.fetch(req)
            return response.wrap(self._session)
        else:
            return req
    def __getattr__(self, name):
        if self._response.has_link(name):
            req = self._response.open_link(name)
            return self._fetch(req)
        if self._response.has_form(name):
            def method(**args):
                req = self._response.submit_form(name, args)
                return self._fetch(req)
            return method
        raise Exception('no')

class Namespace(Navigable):
    pass

class Service(Navigable):
    pass

class Collection(APIClient):
    def __init__(self, response, session=None):
        self._response = response
        self._session = session

    def _fetch(self, req):
        if self._session:
            response = self._session.fetch(req)
            return response.wrap(self._session)
        else:
            return req

    def __getitem__(self, key):
        return self.get(key)

    def get(self, key):
        pass

    def create(self, **args):
        pass

    def delete(self, key):
        pass

    def list(self, **args):
        pass

    def next(self):
        return self.list()

    def where(self, **args):
        pass

    def not_where(self, **args):
        pass

class Session:
    def __init__(self):
        pass

    def fetch(self, request):
        if isinstance(request, str):
            request = APIRequest("GET", request, None, None)

        obj = request.cached
        if not obj:
            data = request.data
            if data is None:
                data = b""
            else:
                content_type, data = objects.Request(data).encode()

            urllib_request= urllib.request.Request(
                url=request.url,
                data=data,
                method=request.verb,
                headers={'Content-Type': objects.CONTENT_TYPE, 'Accept': objects.CONTENT_TYPE},
            )

            with urllib.request.urlopen(urllib_request) as fh:
                base_url = fh.url
                obj = json.load(fh)
        else:
            base_url = request.url

        kind = obj.pop('kind')
        apiVersion = obj.pop('apiVersion')
        metadata = obj.pop('metadata')

        return APIResponse(base_url, kind, apiVersion, metadata, obj)




def open(endpoint):
    session = Session()
    obj = session.fetch(endpoint)
    return obj.wrap(session)

    
