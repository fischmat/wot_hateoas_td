from src import sparql

class UnknownSemanticsException(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class TDInputBuilder(object):
    """
    Builds the input for TD actions.
    Therefore rules what values are desired can be defined and afterwards the input can be automatically determined.
    """

    # Rules for 'free-text' fields
    __value_rules = []

    # Rules for fields with 'option' constraints
    __option_rules = []

    def add_value_rule(self, domain, type, value):
        """
        Adds an rule how to process 'free-text' fields.
        Note that values datatype must also match the one of the type description.

        Example:
        ib = TDInputBuilder()
        ib.add_value_rule('http://someont.de/#Duration', 'http://someont.de/#Second', 5)
        ib.add_value_rule('http://someont.de/#Duration', 'http://someont.de/#Millisecond', 5000)
        input_params = ib.build(some_action)

        This e.g. sets the value accordingly for:
        {
            "type": "integer",
            "dbo:Duration": "dbr:Second"
        }
        or for
        {
            "type": "integer",
            "dbo:Duration": "dbr:Millisecond"
        }
        given the according mappings at the SPARQL endpoint used.

        @type domain str
        @param domain Full IRI the fields value domain must be equivalent to.
        @type type str
        @param type Full IRI the fields value must be equivalent to.
        @param value The value to set in this specific situation.
        """
        self.__value_rules.append((domain, type, value))

    def add_option_rule(self, domain, type):
        """
        Adds an rule how to process fields with 'options' constraints.

        Example:
        ib = TDInputBuilder()
        ib.add_option_rule('http://someont.de/#Color', 'http://someont.de/#Red')
        input_params = ib.build(some_action)

        This sets the value of the field with the following type description to "#ff0000"
        {
            "type": "string",
            "options": [
                {
                    "value": "#0000ff",
                    "dbo:Colour": "dbr:Blue"
                },
                {
                    "value": "#ff0000",
                    "dbo:Colour": "dbr:Red"
                }
            ]
        }
        given the according mappings at the SPARQL endpoint used.

        @type domain str
        @param domain Full IRI of the fields value domain.
        @type type str
        @param type Full IRI of the fields value type.
        """
        self.__option_rules.append((domain, type))

    def __dispatch_value_field(self, ns_repo, key, value, datatype):
        """
        Determines the value of a 'free-text' field using the rules given.
        @return Returns the value imposed by an applicable rule or None if no rule was applicable.
        """
        domain = ns_repo.resolve(key)
        type = ns_repo.resolve(value)
        for rule_domain, rule_type, rule_value in self.__value_rules:
            dt_match = (isinstance(rule_value, int) and datatype == 'integer') \
                       or (isinstance(rule_value, float) and datatype == 'float') \
                       or (isinstance(rule_value, str) and datatype == 'string') \
                       or (isinstance(rule_value, bool) and datatype == 'boolean')

            if dt_match and sparql.classes_equivalent(domain, rule_domain) and sparql.classes_equivalent(type, rule_type):
                return rule_value
        return None

    def __dispatch_options_field(self, ns_repo, options):
        """
        Determines the value of a 'options' constrained field using the rules given.
        @return Returns the value imposed by an applicable rule or None if no rule was applicable.
        """
        for option in options:
            for key, value in option.items():
                if key != 'value':
                    for rule_domain, rule_type in self.__option_rules:
                        domain = ns_repo.resolve(key)
                        type = ns_repo.resolve(value)
                        if sparql.classes_equivalent(domain, rule_domain) and sparql.classes_equivalent(type, rule_type):
                            return option['value']
        return None

    def __dispatch_type_description(self, ns_repo, it):
        """
        Determines the values of the fields using the given type description and the rules registered.
        @return The determined input. (Either primitive type or dict if it['type'] is 'object')
        @raise UnknownSemanticsException If 'it' describes a field of a primitive type and the value for it could
        not be determined or if 'it' describes an object and the latter case is given for any required property.
        """
        if it['type'] != 'object':
            for key, value in it.items():
                if key == 'options':
                    v = self.__dispatch_options_field(ns_repo, it['options'])
                    if v:
                        return v
                    else:
                        raise UnknownSemanticsException('The semantics of none of the options could be determined.')

                elif isinstance(key, str) and isinstance(value, str):
                    v = self.__dispatch_value_field(ns_repo, key, value, it['type'])
                    if v:
                        return v
            raise UnknownSemanticsException('Cannot determine semantics of field.')

        else: # In this case 'it' describes an object.
            o = {}
            for prop_name, prop_desc in it['properties']:
                try:
                    o[prop_name] = self.__dispatch_type_description(ns_repo, prop_desc)
                except UnknownSemanticsException as e:
                    if prop_name in it['required']:
                        raise UnknownSemanticsException('Field %s is required, but semantics cannot be determined.' % prop_name) # If property is required, rethrow exception
            return o

    def build(self, action):
        """
        Determines the values of the fields using the actions type description and the rules registered.
        @return The determined input. (Either primitive type or dict if it['type'] is 'object')
        @raise UnknownSemanticsException If 'it' describes a field of a primitive type and the value for it could
        not be determined or if 'it' describes an object and the latter case is given for any required property.
        """
        it = action.input_type()
        ns_repo = action.get_td().namespace_repository()

        return self.__dispatch_type_description(it)
