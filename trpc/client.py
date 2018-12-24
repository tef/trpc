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
        if self._session:
            url, response = self._session.request(req)
            return self.wrap(response, url, self._session)
        else:
            return req

class Navigable(APIClient):
    def __getattr__(self, name):
        req = self._response.get(name, self._url)
        return self._fetch(req)

class Callable(APIClient):
    def __call__(self, **args):
        req = self._response.call(list(args.items()), self._url)
        return self._fetch(req)

class Namespace(Navigable):
    pass

class Service(Navigable):
    pass

class Procedure(Callable):
    pass

class Collection(APIClient):
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

    def raw_request(self, request):
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
                return fh.url, wire.decode_file(fh, fh.getheader('content-type'))
        else:
            return request.url, wire.decode_object(obj)

    def request(self, request):
        while True:
            url, result = self.raw_request(request)
            if isinstance(result, wire.FutureResult):
                request = result.make_request(url)
            else:
                return url, result

def open(endpoint):
    session = Session()
    url, response = session.request(endpoint)
    return APIClient.wrap(response, url, session)

    
