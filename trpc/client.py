import urllib.request
import sys
import os
import json

from urllib.parse import urljoin, urlencode

from . import wire

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
            response = self._session.request(req)
            return wrap(response, self._session)
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
            response = self._session.request(req)
            return wrap(response, self._session)
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

    def request(self, request):
        if isinstance(request, str):
            request = wire.Request("GET", request, None, None)

        obj = request.cached
        if not obj:
            data = request.data
            if data is None:
                data = b""
            else:
                content_type, data = wire.Arguments(data).encode()

            urllib_request= urllib.request.Request(
                url=request.url,
                data=data,
                method=request.verb,
                headers={'Content-Type': wire.CONTENT_TYPE, 'Accept': wire.CONTENT_TYPE},
            )

            with urllib.request.urlopen(urllib_request) as fh:
                return wire.decode_file(fh, fh.getheader('content-type'), fh.url)
        else:
            return wire.decode_object(obj, request.url)



def open(endpoint):
    session = Session()
    obj = session.request(endpoint)
    return wrap(response, session)

    
