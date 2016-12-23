import json
from enum import Enum
from flask import jsonify

# JSON beautify settings
JSON_INDENT = 2

class Method(Enum):
    '''Contains the four relevant HTTP methods for FormObjects.
    Namely: POST, PUT, PATCH, DELETE
    '''
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"

class LinkObject:
    '''A Link Object is a JSON object that represents a link from the containing resource to a target resource.
    It has three members:
    name (str): Name of this LinkObject
    target_uri (str): Conveys the link target URI as a URI-Reference.
    type (str): Provides a hint indicating what the media type of the result of dereferencing the link should be.
    '''
    def __init__(self, name, target_uri, media_type):
        if isinstance(name, str) and isinstance(target_uri, str) and isinstance(media_type, str):
            self.name = name
            self.target_uri = target_uri
            self.media_type = media_type
        else:
            raise TypeError("name, target_uri and media_type must be of type str!")

    def to_dict(self):
        return {self.name: {"config": {"href": self.target_uri, "type": self.media_type}}}

    def to_json(self):
        return json.dumps(self.to_dict(), sort_keys=False, indent=JSON_INDENT)


class FormObject:
    '''A Form object is a JSON object that represents a form which can be used to perform an action on the
    containing resource. It has four members:
    name (str): Name describing this action (form).
    target_uri: Conveys the form target URI as a URI-Reference.
    method (Enum Method): Specifies the method to use for form submission ("POST", "PUT", "PATCH" or "DELETE")
    media_type (str): Specifies the media type acceptable for the representation to be enclosed in the request
    message payload as part of form submission.
    '''
    def __init__(self, name, target_uri, method, media_type):
        if not isinstance(name, str):
            raise TypeError("name must be of type str!")
        if not isinstance(target_uri, str):
            raise TypeError("target_uri must be of type str!")
        if not isinstance(method, Method):
            raise TypeError("method must be of type Method!")
        if not isinstance(media_type, str):
            raise TypeError("media_type must be of type str!")
        self.name = name
        self.target_uri = target_uri
        self.method = method
        self.media_type = media_type

    def to_dict(self):
        return {self.name: {"href": self.target_uri, "method": str(self.method.value), "accept": self.media_type}}

    def to_json(self):
        return json.dumps(self.to_dict(), sort_keys=False, indent=JSON_INDENT)

class ResourceObject:
    '''A ResourceObject is a JSON object that represents a resource. It has four members:
    base (string): specifies a base URI for relative references.
    links ([LinkObject]): Contains links that reference other resources that are related to the resource. (see description of LinkObject)
    forms ([FormObject]): Contains forms that describe action that can be performed on the resource. (see description of FormObject)
    embedded: Contains embedded resources.
    For a more detailed description see: Hartke. "CoRE Lighting".
    '''

    links = []
    forms = []

    def __init__(self, base, links, forms, embedded):
        if not isinstance(base, str):
            raise TypeError("base must be of type str!")
        if not isinstance(links, list) or len(links) > 0 and any(not isinstance(x, LinkObject) for x in links):
            raise TypeError("links must be list of LinkObject")
        if not isinstance(forms, list) or len(forms) > 0 and any(not isinstance(x, FormObject) for x in forms):
            raise TypeError("forms must be list of FormObject")
        # TODO: validate embedded

        # Prepend base url before link/ form objects.
        for lo in links:
            lo.target_uri = base + lo.target_uri
        for fo in forms:
            fo.target_uri = base + fo.target_uri

        self.base = base
        self.links += links
        self.forms += forms
        self.embedded = embedded

    def to_json(self):
        resource = {}
        # Links.
        if len(self.links) > 0:
            links_dict = {}
            for link in self.links:
                links_dict.update(link.to_dict())
            resource["_links"] = links_dict

        # Forms
        if len(self.forms) > 0:
            forms_dict = {}
            for form in self.forms:
                forms_dict.update(form.to_dict())
            resource["_forms"] = forms_dict

        return jsonify(resource)


