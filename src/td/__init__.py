import json
from http.client import HTTPConnection
from urllib.parse import urlparse

from src import sparql
from src.sparql import SPARQLNamespaceRepository

class ThingDescription(object):
    """
    Class representing the thing description of a thing.
    """

    __td = dict()

    __ns_repo = None

    def __init__(self, td):
        """
        @param td: The TD as either a JSON-string or deserialized JSON.
        """
        super().__init__()
        if isinstance(td, str):
            td = json.loads(td)
        self.__td = td

    def namespace_repository(self):
        """
        Returns the namespace repository of the TD.
        See sparql.SPARQLNamespaceRepository
        """
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
        """
        Returns the property with a specific name or None if there is none with this name.
        """
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
        """
        Returns a list of URIs this TD is available at.
        """
        return self.__td['uris']


def _validate_input_string(self, vt, value):
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
        raise ValueError("Type of property is string but %s given!" % str(type(value)))


def _validate_input_number(self, vt, value):
    if isinstance(value, float) or isinstance(value, int):
        if 'minimum' in vt.keys() and value < vt['minimum']:
            raise ValueError("Value %f violates minimum constraint of %f" % (float(value), float(vt['minimum'])))

        if 'maximum' in vt.keys() and value > vt['maximum']:
            raise ValueError("Value %f violates maximum constraint of %f" % (float(value), float(vt['maximum'])))
    else:
        raise ValueError("Type of property is number but %s given!" % str(type(value)))


def _validate_input_object(self, vt, o):
    if isinstance(o, dict):
        for prop_name, prop_vt in vt['properties'].items():
            if prop_name in o.keys():
                if prop_vt['type'] == 'string':
                    _validate_input_string(prop_vt, o[prop_name])

                elif prop_vt['type'] == 'number' or prop_vt['type'] == 'integer' or prop_vt['type'] == 'float':
                    _validate_input_number(prop_vt, o[prop_name])

                elif prop_vt['type'] == 'object':
                    _validate_input_object(prop_vt, o[prop_name])

            elif prop_name in vt['required']:
                raise ValueError("Object missing required property %s" % prop_name)
    else:
        raise ValueError("Type of property is object but %s given!" % str(type(o)))


class TDProperty(object):
    """
    A property of a TD.
    """

    __td = None # The ThingDescription this property is part of.

    __prop = dict() # The propery as deserialized JSON (dict)

    def __init__(self, td, prop):
        """
        @type td ThingDescription
        @param td The TD this property belongs to.
        @type prop dict
        @param prop The property as deserialized JSON.
        """
        super().__init__()
        self.__td = td
        self.__prop = prop

    def type(self):
        """
        @rtype str|None
        @return The type of this property as a full IRI if there is a @type annotation. Otherwise None.
        """
        if '@type' in self.__prop.keys():
            return self.__td.namespace_repository().resolve(self.__prop['@type'])
        else:
            return None

    def name(self):
        """
        @rtype str|None
        @return The name of this property if there is one. Otherwise None.
        """
        if 'name' in self.__prop.keys():
            return self.__prop['name']
        else:
            return None

    def value_type(self):
        """
        @rtype dict
        @return The value type definition of this property as deserialized JSON schema or None
        if there is no valueType annotation in the TD.
        """
        if 'valueType' in self.__prop.keys():
            return self.__prop['valueType']
        else:
            return None

    def writeable(self):
        """
        @rtype bool
        @return Returns whether this property is writeable (True) or not (False).
        Returns None if this property has no writable annotation.
        """
        if 'writeable' in self.__prop.keys():
            return self.__prop['writeable']
        else:
            return None

    def hrefs(self):
        """
        @rtype list
        @return The list of relative references to this property.
        """
        if 'hrefs' in self.__prop.keys():
            return self.__prop['hrefs']
        else:
            return None

    def url(self, proto='http'):
        """
        Resolves the full URL of the property for a given protocol.
        @type proto str
        @param proto The protocol for which an URL should be returned.
        @rtype str
        @return Returns the full URL for the given protocol or None if there is none.
        """
        for i, base_url in enumerate(self.__td.uris()):
            base_url_parsed = urlparse(base_url)
            if base_url_parsed.scheme == proto:
                if base_url[-1] == '/':
                    return base_url + self.__prop['hrefs'][i]
                else:
                    return base_url + '/' + self.__prop['hrefs'][i]
        return None

    def __value_plain(self):
        """
        @rtype str
        @returns Plain string representation of the value.
        """
        url = urlparse(self.url())
        conn = HTTPConnection(url.netloc)
        conn.request('GET', url.path)
        response = conn.getresponse()
        if response.code == 200:
            return response.read().decode('utf-8')
        else:
            raise Exception("Received %d %s requesting %s" % (response.code, response.status, self.url()))

    def value(self):
        """
        @return The value of the property in the type specified in the TD. (e.g. 'number' -> int, 'object' -> dict)
        """
        v = self.__value_plain()
        vt = self.value_type()

        if vt['type'] == 'number' or vt['type'] == 'float':
            return float(v)
        elif vt['type'] == 'integer':
            return int(v)
        elif vt['type'] == 'object':
            return json.loads(v)
        else:
            raise Exception("Unknown property type %s" % vt['type'])

    def __set_plain(self, value):
        """
        @type value str
        @param value The plain string representation of the value to set.
        """
        url = urlparse(self.url())
        conn = HTTPConnection(url.netloc)
        conn.request('POST', url.path, body=value)
        response = conn.getresponse()
        if response.code == 200:
            return True
        else:
            return False

    def set(self, value):
        """
        Validates an value whether it satisfies the constraints given by the TD and sets it.
        @type value str|float|int|dict
        @param value The value to set (of required type and format).
        @raise ValueError If value does not satisfy the constraints given by the TD.
        """
        vt = self.value_type()
        if vt['type'] == 'string':
            with _validate_input_string(vt, value):
                self.__set_plain(value)

        elif vt['type'] == 'number' or vt['type'] == 'integer' or vt['type'] == 'float':
            with _validate_input_number(vt, value):
                self.__set_plain(str(value))

        elif vt['type'] == 'object':
            with _validate_input_object(vt, value):
                self.__set_plain(json.dumps(value))
        else:
            raise Exception("Property has unknown type %s" % vt['type'])
