from src import sparql

class UnknownSemanticsException(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class InputTypeBuilder(object):

    __value_rules = []

    __option_rules = []

    def add_value_rule(self, domain, type, value):
        self.__value_rules.append((domain, type, value))

    def add_option_rule(self, domain, type):
        self.__option_rules.append((domain, type))

    def __dispatch_value_field(self, ns_repo, key, value, datatype):
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
        it = action.input_type()
        ns_repo = action.get_td().namespace_repository()

        return self.__dispatch_type_description(it)
