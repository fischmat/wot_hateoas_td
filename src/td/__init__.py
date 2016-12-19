import json
from http.client import HTTPConnection
from urllib.parse import urlparse

from src import sparql
from src.sparql import SPARQLNamespaceRepository


class ThingDescription(object):

    __td = dict()

    __ns_repo = None

    def __init__(self, td):
        super().__init__()
        self.__td = td

    def namespace_repository(self):
        if self.__ns_repo is not None:
            return self.__ns_repo
        else:
            self.__ns_repo = SPARQLNamespaceRepository()
            for context in self.__td['@context']:
                if isinstance(context, dict):
                    for shorthand, prefix in context.items():
                        self.__ns_repo.register(shorthand, prefix)
            return self.__ns_repo


    def get_property_by_name(self, name):
        for prop in self.__td['properties']:
            if 'name' in prop.keys() and prop['name'] == name:
                return prop
        return None

    def get_property_by_types(self, types):
        """
        Returns properties equivalent to any of the given types.
        @param types List of IRIs.
        @return Any property equivalent to any given type or None if none found.
        """
        ns_repo = self.namespace_repository()

        for prop in self.__td['properties']:
            if '@type' in prop.keys():
                if ns_repo.resolve(prop['@type']) in types:
                    return TDProperty(self, prop)
                else:
                    for type in types:
                        if sparql.classes_equivalent(type, ns_repo.resolve(prop['@type'])):
                            return TDProperty(self, prop)
        return None

    def uris(self):
        return self.__td['uris']

class TDProperty(object):

    __td = None

    __prop = dict()

    def __init__(self, td, prop):
        super().__init__()
        self.__td = td
        self.__prop = prop

    def type(self):
        if '@type' in self.__prop.keys():
            return self.__prop['@type']
        else:
            return None

    def name(self):
        if 'name' in self.__prop.keys():
            return self.__prop['name']
        else:
            return None

    def value_type(self):
        if 'valueType' in self.__prop.keys():
            return self.__prop['valueType']
        else:
            return None

    def writeable(self):
        if 'writeable' in self.__prop.keys():
            return self.__prop['writeable']
        else:
            return None

    def hrefs(self):
        if 'hrefs' in self.__prop.keys():
            return self.__prop['hrefs']
        else:
            return None

    def url(self, proto='http'):
        for i, base_url in enumerate(self.__td.uris()):
            base_url_parsed = urlparse(base_url)
            if base_url_parsed.scheme == proto:
                if base_url[-1] == '/':
                    return base_url + self.__prop['hrefs'][i]
                else:
                    return base_url + '/' + self.__prop['hrefs'][i]
        return None

    def value_plain(self):
        url = urlparse(self.url())
        conn = HTTPConnection(url.netloc)
        conn.request('GET', url.path)
        response = conn.getresponse()
        if response.code == 200:
            return response.read().decode('utf-8')
        else:
            raise Exception("Received %d %s requesting %s" % (response.code, response.status, self.url()))

    def __set_plain(self, value):
        url = urlparse(self.url())
        conn = HTTPConnection(url.netloc)
        conn.request('POST', url.path, body=value)
        response = conn.getresponse()
        if response.code == 200:
            return True
        else:
            return False

    def set(self, value):
        # TODO implement complex input types.
        vt = self.value_type()
        if vt['type'] == 'string':
            if isinstance(value, str):
                # Any constraints?
                if 'enum' in vt.keys():
                    if value in vt['enum']:
                        return self.__set_plain(value)
                    else:
                        raise ValueError("Value %s not allowed (not in enum)" % value)
                elif 'options' in vt.keys():
                    if value in [o['value'] for o in vt['options']]:
                        return self.__set_plain(value)
                    else:
                        raise ValueError("Value %s not allowed (options constraint)" % value)
                else:
                    return self.__set_plain(value)
            else:
                raise ValueError("Type of property is string but %s given!" % str(type(value)))
        else:
            raise Exception("Not yet implemented!")
