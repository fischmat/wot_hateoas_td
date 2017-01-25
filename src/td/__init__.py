# Module td
# Provides classes for convinient handling Thing Description
#
# Author: Matthias Fisch
#
#

import json
import threading
from copy import deepcopy
from http.client import HTTPConnection
from urllib.parse import urlparse

import time
import http.client as httplib

from src import sparql
from src.sparql import SPARQLNamespaceRepository

def get_thing_description_from_url(url):
    """
        Fetches and deserializes the thing description that can be found at a certain URL.
        @type url str
        @param url The URL where the TD is located.
        @rtype ThingDescription
        @return The TD.
        """
    url_parsed = urlparse(url)

    conn = httplib.HTTPConnection(url_parsed.netloc)
    conn.request('GET', url_parsed.path)
    response = conn.getresponse()
    if response.code == 200:
        return ThingDescription(json.loads(response.read().decode('utf-8')))
    else:
        raise Exception("Received %d %s requesting %s" % (response.code, response.status, url))

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

    def type_equivalent_to(self, types):
        """
        Checks whether the @type of this thing is equvalent to any of the given types.
        @param types List of IRIs (either full or shorthands with prefixes defined in this TD)
        @return Returns True if any of the types given is equivalent to @type of this TD. Returns False
        if none of them is or @type is not set in this TD.
        """
        if '@type' in self.__td.keys():
            for type in types:
                if sparql.classes_equivalent(self.__ns_repo.resolve(self.__td['@type'],
                                                                    self.__ns_repo.resolve(type))):
                    return True
            return False
        else:
            return False

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

    def get_action_by_types(self, types):
        """
        Returns actions equivalent to any of the given types.
        @param types List of IRIs.
        @return Any action equivalent to any given type or None if none found.
        """
        ns_repo = self.namespace_repository()

        for action in self.__td['actions']:
            if '@type' in action.keys():
                if ns_repo.resolve(action['@type']) in types:
                    return TDAction(self, action)
                else:
                    for type in types:
                        if sparql.classes_equivalent(type, ns_repo.resolve(action['@type'])):
                            return TDAction(self, action)
        return None

    def get_event_by_types(self, types):
        """
        Returns events equivalent to any of the given types.
        @param types List of IRIs.
        @return Any event equivalent to any given type or None if none found.
        """
        ns_repo = self.namespace_repository()

        for event in self.__td['events']:
            if '@type' in event.keys():
                if ns_repo.resolve(event['@type']) in types:
                    return TDEvent(self, event)
                else:
                    for type in types:
                        if sparql.classes_equivalent(type, ns_repo.resolve(event['@type'])):
                            return TDEvent(self, event)
        return None

    def has_all_properties_of(self, types):
        """
        Checks if this thing has an equivalent property for any of the given types.
        @param types List of IRIs.
        @rtype bool
        @return Returns True iff there is an equivalent property for every given type.
        """
        ns_repo = self.namespace_repository()

        for type in types:
            found_matching_prop = False
            for prop in self.__td['properties']:
                if '@type' in prop.keys():
                    if sparql.classes_equivalent(ns_repo.resolve(type), ns_repo.resolve(prop['@type'])):
                        found_matching_prop = True
            if not found_matching_prop:
                return False
        return True

    def has_any_property_of(self, types):
        """
        Checks if this thing has an equivalent property for at least one of the given types.
        @param types List of IRIs.
        @rtype bool
        @return Returns True iff there is an equivalent property for at least one of the given types.
        """
        return self.get_property_by_types(types) is not None

    def has_all_actions_of(self, types):
        """
        Checks if this thing has an equivalent action for any of the given types.
        @param types List of IRIs.
        @rtype bool
        @return Returns True iff there is an equivalent action for every given type.
        """
        ns_repo = self.namespace_repository()

        for type in types:
            found_matching_action = False
            for action in self.__td['actions']:
                if '@type' in action.keys():
                    if sparql.classes_equivalent(ns_repo.resolve(type), ns_repo.resolve(action['@type'])):
                        found_matching_action = True
            if not found_matching_action:
                return False
        return True

    def has_any_action_of(self, types):
        """
        Checks if this thing has an equivalent action for at least one of the given types.
        @param types List of IRIs.
        @rtype bool
        @return Returns True iff there is an equivalent action for at least one of the given types.
        """
        return self.get_action_by_types(types) is not None

    def has_all_events_of(self, types):
        """
        Checks if this thing has an equivalent event for any of the given types.
        @param types List of IRIs.
        @rtype bool
        @return Returns True iff there is an equivalent event for every given type.
        """
        ns_repo = self.namespace_repository()

        for type in types:
            found_matching_event = False
            for event in self.__td['events']:
                if '@type' in event.keys():
                    if sparql.classes_equivalent(ns_repo.resolve(type), ns_repo.resolve(event['@type'])):
                        found_matching_event = True
            if not found_matching_event:
                return False
        return True

    def has_any_event_of(self, types):
        """
        Checks if this thing has an equivalent event for at least one of the given types.
        @param types List of IRIs.
        @rtype bool
        @return Returns True iff there is an equivalent event for at least one of the given types.
        """
        return self.get_event_by_types(types) is not None

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
        raise ValueError("Value type definition imposes string but %s given!" % str(type(value)))


def _validate_input_number(self, vt, value):
    if isinstance(value, float) or isinstance(value, int):
        if 'minimum' in vt.keys() and value < vt['minimum']:
            raise ValueError("Value %f violates minimum constraint of %f" % (float(value), float(vt['minimum'])))

        if 'maximum' in vt.keys() and value > vt['maximum']:
            raise ValueError("Value %f violates maximum constraint of %f" % (float(value), float(vt['maximum'])))
    else:
        raise ValueError("Value type definition imposes number but %s given!" % str(type(value)))


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
        raise ValueError("Value type definition imposes object but %s given!" % str(type(o)))

def _is_url(s):
    """
    Checks whether s is an URL.
    @return True if s is an URL. False otherwise.
    """
    parsed = urlparse(s)
    if parsed.netloc:
        return True
    else:
        return False

def _ns_resolve_input_type(input_type, ns_repo):
    if isinstance(input_type, dict):
        input_type_copy = {}
        for key in input_type.keys():
            input_type_copy[_ns_resolve_input_type(key, ns_repo)] = _ns_resolve_input_type(input_type[key], ns_repo)
        return input_type_copy

    elif isinstance(input_type, str) and _is_url(input_type):
        return ns_repo.resolve(input_type)
    else:
        return deepcopy(input_type)

def _parse_raw_response(v, vt):
    """
    Converts an response of a thing (e.g. property value) to the datatype corresponding the valueType definition given.
    @type v str
    @param v Raw value.
    @type vt dict
    @param vt The value type definition for v.
    @return The parsed value.
    @raise Exception Raised if the value type definition imposes an unknown type.
    """
    if vt['type'] == 'number' or vt['type'] == 'float':
        return float(v)
    elif vt['type'] == 'integer':
        return int(v)
    elif vt['type'] == 'object':
        return json.loads(v)
    else:
        raise Exception("Value type definition imposes unknown type %s" % vt['type'])

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

    def get_td(self):
        """
        @rtype ThingDescription
        @return The thing description this property belongs to.
        """
        return self.__td

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
            return _ns_resolve_input_type(self.__prop['valueType'], self.__td.namespace_repository())
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

        return _parse_raw_response(v, vt)

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

class TDAction:
    """
    An action of a TD.
    """

    __td = None  # The ThingDescription this action is part of.

    __action = dict()  # The action as deserialized JSON (dict)

    def __init__(self, td, action):
        self.__td = td
        self.__action = action

    def get_td(self):
        """
        @rtype ThingDescription
        @return The thing description this action belongs to.
        """
        return self.__td

    def type(self):
        if '@type' in self.__action.keys():
            return self.__td.namespace_repository().resolve(self.__action['@type'])
        else:
            return None

    def name(self):
        if 'name' in self.__action.keys():
            return self.__action['name']
        else:
            return None

    def input_value_type(self):
        if 'inputData' in self.__action.keys():
            return _ns_resolve_input_type(self.__action['inputData'], self.__td.namespace_repository())
        else:
            return None

    def output_value_type(self):
        if 'outputData' in self.__action.keys():
            return _ns_resolve_input_type(self.__action['outputData'], self.__td.namespace_repository())
        else:
            return None

    def hrefs(self):
        """
        @rtype list
        @return The list of relative references to this action.
        """
        if 'hrefs' in self.__action.keys():
            return self.__action['hrefs']
        else:
            return None

    def url(self, proto='http'):
        """
        Resolves the full URL of the action for a given protocol.
        @type proto str
        @param proto The protocol for which an URL should be returned.
        @rtype str
        @return Returns the full URL for the given protocol or None if there is none.
        """
        for i, base_url in enumerate(self.__td.uris()):
            base_url_parsed = urlparse(base_url)
            if base_url_parsed.scheme == proto:
                hrefs = self.hrefs()
                if hrefs is not None:
                    if base_url[-1] == '/':
                        return base_url + hrefs[i]
                    else:
                        return base_url + '/' + hrefs[i]
        return None

    def __invoke_plain(self, plain_data):
        url = urlparse(self.url())
        conn = HTTPConnection(url.netloc)
        conn.request('POST', url.path, body=plain_data)
        response = conn.getresponse()
        if response.code != 200:
            raise Exception("Received error code %d %s when invoking action %s" % (response.code, response.status, self.url()))
        else:
            return response.read().decode('utf-8')

    def invoke(self, input_data):
        ivt = self.input_value_type()
        ovt = self.output_value_type()
        if ivt['type'] == 'string':
            with _validate_input_string(ivt, input_data):
                out_plain = self.__invoke_plain(input_data)
                if ovt:
                    return _parse_raw_response(out_plain, ovt)

        elif ivt['type'] == 'number' or ivt['type'] == 'integer' or ivt['type'] == 'float':
            with _validate_input_number(ivt, input_data):
                out_plain = self.__invoke_plain(str(input_data))
                if ovt:
                    return _parse_raw_response(out_plain, ovt)

        elif ivt['type'] == 'object':
            with _validate_input_object(ivt, input_data):
                out_plain = self.__invoke_plain(json.dumps(input_data))
                if ovt:
                    return _parse_raw_response(out_plain, ovt)
        else:
            raise Exception("Action has unknown input data type %s" % ivt['type'])

class TDEvent(object):
    """
    An event of a TD.
    """

    __td = None  # The ThingDescription this event is part of.

    __event = dict()  # The event as deserialized JSON (dict)

    def __init__(self, td, event):
        """
        @type td ThingDescription
        @param td The TD this event belongs to.
        @type event dict
        @param event The event as deserialized JSON.
        """
        super().__init__()
        self.__td = td
        self.__event = event

    def get_td(self):
        """
        @rtype ThingDescription
        @return The thing description this event belongs to.
        """
        return self.__td

    def type(self):
        """
        @rtype str|None
        @return The type of this event as a full IRI if there is a @type annotation. Otherwise None.
        """
        if '@type' in self.__event.keys():
            return self.__td.namespace_repository().resolve(self.__event['@type'])
        else:
            return None

    def name(self):
        """
        @rtype str|None
        @return The name of this event if there is one. Otherwise None.
        """
        if 'name' in self.__event.keys():
            return self.__event['name']
        else:
            return None

    def value_type(self):
        """
        @rtype dict
        @return The value type definition of this event as deserialized JSON schema or None
        if there is no valueType annotation in the TD.
        """
        if 'valueType' in self.__event.keys():
            return _ns_resolve_input_type(self.__event['valueType'], self.__td.namespace_repository())
        else:
            return None


    def hrefs(self):
        """
        @rtype list
        @return The list of relative references to this event.
        """
        if 'hrefs' in self.__event.keys():
            return self.__event['hrefs']
        else:
            return None

    def url(self, proto='http'):
        """
        Resolves the full URL of the event for a given protocol.
        @type proto str
        @param proto The protocol for which an URL should be returned.
        @rtype str
        @return Returns the full URL for the given protocol or None if there is none.
        """
        for i, base_url in enumerate(self.__td.uris()):
            base_url_parsed = urlparse(base_url)
            if base_url_parsed.scheme == proto:
                if base_url[-1] == '/':
                    return base_url + self.__event['hrefs'][i]
                else:
                    return base_url + '/' + self.__event['hrefs'][i]
        return None

    def subscribe(self, conf_data = None, poll_interval=200):
        # Serialize data according to valueType of the TD:
        if isinstance(conf_data, dict):
            serialized_conf = json.dumps(conf_data)
        elif isinstance(conf_data, str):
            serialized_conf = conf_data
        else:
            serialized_conf = None

        # Get the HTTP-URL of this event:
        url = self.url(proto='http')
        if not url:
            raise Exception("HTTP is not supported for this event!")

        # Do a POST request:
        url_parse = urlparse(url)
        conn = HTTPConnection(url_parse.netloc)
        conn.request('POST', url_parse.path, body=serialized_conf)
        response = conn.getresponse()

        # Thing should create a new resource and redirect to it:
        if response.code != 308:
            raise Exception(
                "Received HTTP code %d %s, but expected 308 Permanent Redirect when invoking action %s" % (response.code, response.status, self.url()))
        else:
            # Build the full URI of the created resource:
            subscription_uri = None
            for base_url in self.__td.uris():
                base_url_parsed = urlparse(base_url)
                if base_url_parsed.scheme == 'http':
                    subscription_uri = base_url + response.headers['Location']

            if subscription_uri:
                return EventSubscription(subscription_uri, self.value_type(), poll_interval)
            else:
                raise Exception("Thing does not support HTTP.")

class EventSubscription(object):
    def __init__(self, uri, value_type, poll_interval):
        self.__uri = uri
        self.__value_type = value_type
        self.__poll_interval = poll_interval
        self.__valid = True
        self.__error_callback = None

    def start(self, callback, error_callback = None):
        """
        Start observation of the event resource.
        """
        # Start polling routine as new daemon thread:
        poll_thread = threading.Thread(target=self.__poll, args=(callback, ))
        poll_thread.daemon = True
        poll_thread.start()

    def __poll(self, callback):
        url_parsed = urlparse(self.__uri)

        while self.__valid:
            conn = HTTPConnection(url_parsed.netloc)
            conn.request('GET', url_parsed.path)
            response = conn.getresponse()
            if response.code == 200:
                raw = response.read().decode('utf-8')

                # Accoring to W3C IG Common Practices, the value is sent as the value of an objects "value" field:
                response_object = json.loads(raw)
                if response_object and 'value' in response_object:
                    if callback:
                        # Invoke callback routine with data from the value field:
                        callback(response_object['value'])
                else:
                    print("Received invalid response. Should be object with 'value' field, %s received" % raw)

            elif response.code != 208 and self.__error_callback:
                self.__error_callback("Received %d %s on request for subscribed resource %s" % (
                response.code, response.status, self.__uri))

            time.sleep(self.__poll_interval/1000.0)

    def invalidate(self):
        self.__valid = False

    def set_error_callback(self, error_callback):
        self.__error_callback = error_callback