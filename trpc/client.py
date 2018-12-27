import urllib.request
import sys
import os
import json

from urllib.parse import urljoin, urlencode

from . import wire

class APIClient:
    Kinds = {}
    def __init__(self, response, url, session=None):
        self._url = url
        self._response = response
        self._session = session

    def __init_subclass__(cls):
        cls.Kinds[cls.__name__] = cls

    @classmethod
    def wrap(cls, response, url, session):
        if response.kind == 'Result':
            return response.value
        c = cls.Kinds.get(response.kind, cls)
        return c(response, url, session)

    def _fetch(self, req):
        url, response = self._session.request(req, self._url)
        return self.wrap(response, url, self._session)

class Navigable(APIClient):
    def __getattr__(self, name):
        req = self._response.walk(name)
        return self._fetch(req)

class Callable(APIClient):
    def __call__(self, **args):
        req = self._response.call(args)
        return self._fetch(req)

class Namespace(Navigable):
    pass

class Service(Navigable):
    pass

class Procedure(Callable):
    pass

class ResultSet(APIClient):
    def __iter__(self):
        obj, url = self._response, self._url
        while obj is not None:
            for item in obj.values:
                yield item

            req = obj.request_next()
            if req:
                url, obj = self._session.request(req, url)
            else:
                obj = None

class Model(APIClient):
    def __getitem__(self, key):
        return self.get(key)

    def get(self, key):
        req = self._response.get_entry(key)
        return self._fetch(req)

    def create(self, **args):
        req = self._response.create_entry(args)
        return self._fetch(req)

    def delete(self, key):
        req = self._response.delete_entry(key)
        return self._fetch(req)

    def all(self):
        req = self._response.get_where(None)
        return self._fetch(req)

    def next(self):
        return self.list()

    def where(self, **args):
        pass

    def not_where(self, **args):
        pass

class Session:
    def __init__(self):
        pass

    def raw_request(self, request, base_url=None, cached=None):
        headers = {'Accept': wire.CONTENT_TYPE}
        if isinstance(request, str):
            request = wire.HTTPRequest("GET", request, {}, headers, None, None, cached)
        elif isinstance(request, wire.Request):
            request = request.make_http(base_url)

        obj = request.cached

        if obj is None:
            if request.content_type:
                headers['Content-Type'] = request.content_type
            if request.headers:
                headers.update(request.headers)
            urllib_request= urllib.request.Request(
                url=request.url,
                data=request.data,
                method=request.method,
                headers=headers
            )

            with urllib.request.urlopen(urllib_request) as fh:
                return fh.url, wire.decode_file(fh, fh.getheader('content-type'))
        else:
            return request.url, wire.decode_object(obj)

    def request(self, request, base_url= None):
        """ Handle redirects, futures """
        url = base_url
        while True:
            url, result = self.raw_request(request, url)
            if isinstance(result, wire.FutureResult):
                request = result.make_request()
            else:
                return url, result

def open(endpoint, schema=None):
    session = Session()
    url, response = session.request(request, cached=schema)
    return APIClient.wrap(response, url, session)

    
