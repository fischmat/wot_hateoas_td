# sparql module
# Defines functionality to perform certain queries
# The endpoint used is lov.okfn.org
from urllib.parse import urlparse

from SPARQLWrapper import SPARQLWrapper, JSON

# The URL of the default SPARQL endpoint. Assume Bigdata Blazegraph is runn
DEFAULT_SPARQL_ENDPOINT = 'http://localhost:9999/bigdata/namespace/wotkb/sparql'

class SparqlException(Exception):
    """
    Exception to signalize that something went wrong during a query to a SPARQL-endpoint.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class UnknownPrefixException(SparqlException):
    """
    Signalizes that a shorthand IRI should be resolved from an unknown prefix.
    """
    pass

class SPARQLNamespaceRepository(object):
    """
    Utility class for resolving shorthand notation for IRIs, e.g. dogont:Lighting to
    http://elite.polito.it/ontologies/dogont.owl#Lighting.

    Example:
        ns = SPARQLNamespaceRepository()
        ns.register('dogont', 'http://elite.polito.it/ontologies/dogont.owl#')
        ns.resolve('dogont:Lighting')
        > http://elite.polito.it/ontologies/dogont.owl#Lighting
    """
    __prefixes = {}

    def register(self, prefix_name, prefix):
        """
        Register a shorthand for a IRI-prefix.
        @type prefix_name str
        @param prefix_name The shorthand name of the prefix, e.g. dogont.
        @type prefix str
        @param prefix The full prefix, e.g. http://elite.polito.it/ontologies/dogont.owl#.
        """
        self.__prefixes[prefix_name] = prefix

    def resolve(self, shorthand):
        """
        Resolves a shorthand notation of an IRI using a previously registered prefix.
        @type shorthand str
        @param shorthand A shorthand IRI, e.g. dogont:Lighting
        @rtype str
        @return The full IRI.
        @raise UnknownPrefixException If the used prefix was not previously registered.
        @raise ValueError If the shorthand is malformed, i.e. not '<prefix>:<resource>'.
        """
        # First check if this is already a
        parsed = urlparse(shorthand)
        if parsed.scheme and parsed.netloc:
            return shorthand

        try:
            prefix, resource = shorthand.split(':')
            if prefix in self.__prefixes.keys():
                return self.__prefixes[prefix] + resource
            else:
                raise UnknownPrefixException('The IRI-prefix %s is unknown by this repository' % prefix)

        except ValueError:
            raise ValueError('%s is not a valid IRI-shorthand.' % shorthand)


def __query(q, endpoint = DEFAULT_SPARQL_ENDPOINT):
    """
    Files a query to the SPARQL-endpoint at lov.okfn.org
    @type q: str
    @param q: A SPARQL query.
    @type endpoint str
    @param endpoint URL of the SPARQL endpoint to query.
    @rtype: dict|None
    @return: The response of the endpoint or None on error or malformed query.
    """
    sparql = SPARQLWrapper(endpoint, returnFormat=JSON)
    sparql.setQuery(q)
    r = sparql.query().convert()

    if isinstance(r, dict): # Check whether JSON conversion was successful
        return r
    else:
        raise SparqlException("SPARQL endpoint %s does not support JSON return format." % endpoint)


def equivalent_classes(iri, endpoint = DEFAULT_SPARQL_ENDPOINT):
    """
    Queries the SPARQL-endpoint for classes/resources that are equal to the one given.
    Takes equivalency by the transitive closure of rdfs:seeAlso, owl:sameAs and owl:equivalentClass into account.
    @type iri: str
    @param iri: The IRI of the class for which equivalent classes should be found.
    @type endpoint str
    @param endpoint URL of the SPARQL endpoint to query.
    @rtype: list
    @return: List of the IRIs of equivalent classes.
    @raise SparqlException: Raised if the internally constructed query is malformed or the response of the endpoint is.
    """
    q = 'PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>\
         PREFIX owl: <http://www.w3.org/2002/07/owl#>\
         SELECT DISTINCT ?o {\
                 { <' + iri + '> rdfs:seeAlso+ ?o .} \
                UNION { <' + iri + '> owl:sameAs+ ?o . } \
                 UNION { <' + iri + '> owl:equivalentClass+ ?o .} \
                UNION { ?o rdfs:seeAlso+ <' + iri + '>.} \
                UNION { ?o owl:sameAs+ <' + iri + '> . } \
                 UNION { ?o owl:equivalentClass+ <' + iri + '> .}}'

    try:
        r = __query(q, endpoint)
    except ValueError:
        raise SparqlException('Malformed query: %s' % q)

    if r and 'results' in r and 'bindings' in r['results']:
        eq_classes = []
        for binding in r['results']['bindings']:
            if 'o' in binding and binding['o']['type'] == 'uri':
                eq_classes.append(binding['o']['value'])
        return eq_classes
    else:
        raise SparqlException('Malformed response')


def classes_equivalent(iri1, iri2, endpoint = DEFAULT_SPARQL_ENDPOINT):
    """
    Queries the SPARQL-endpoint for equivalency of two classes/resources.
    Takes equivalency by the transitive closure of rdfs:seeAlso, owl:sameAs and owl:equivalentClass into account.
    @type iri1: str
    @param iri1: The IRI of the first class/resource.
    @type iri2: str
    @param iri2: The IRI of the second class/resource.
    @type endpoint str
    @param endpoint URL of the SPARQL endpoint to query.
    @rtype: bool
    @return: Returns true if the classes/resources are equivalent.
    @raise SparqlException: Raised if the internally constructed query is malformed or the response of the endpoint is.
    """
    q = 'PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#> \
        PREFIX owl: <http://www.w3.org/2002/07/owl#> \
        ASK {\
                 { <' + iri1 + '> rdfs:seeAlso ?samid . \
                   ?samid rdfs:seeAlso* <' + iri2 + '> } \
                UNION { <' + iri1 + '> owl:sameAs+ <' + iri2 + '> . } \
                UNION { <' + iri1 + '> owl:equivalentClass+ <' + iri2 + '> .} \
                UNION { <' + iri2 + '> rdfs:seeAlso+ <' + iri1 + '>.} \
                UNION { <' + iri2 + '> owl:sameAs+ <' + iri1 + '> . } \
                UNION { <' + iri2 + '> owl:equivalentClass+ <' + iri1 + '> .} \
        }'

    try:
        r = __query(q, endpoint)
    except ValueError:
        raise SparqlException('Malformed query %s' % q)

    if 'boolean' in r:
        return r['boolean']
    else:
        raise SparqlException('Malformed response')

def shared_superclasses(iri1, iri2, endpoint = DEFAULT_SPARQL_ENDPOINT):
    """
    Queries the SPARQL endpoint for common superclasses. Those can have any distance in the inheritance tree.
    @param iri1: The IRI of the first class/resource.
    @type iri2: str
    @param iri2: The IRI of the second class/resource.
    @type endpoint str
    @param endpoint URL of the SPARQL endpoint to query.
    @rtype list
    @return A list of the IRIs of common superclasses.
    """
    q = 'PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>\
         PREFIX owl: <http://www.w3.org/2002/07/owl#>\
         SELECT DISTINCT ?super { \
              <' + iri1 + '> rdfs:subClassOf+ ?super . \
              <' + iri2 + '> rdfs:subClassOf+ ?super . \
         }'

    try:
        r = __query(q, endpoint)
    except ValueError:
        raise SparqlException('Malformed query: %s' % q)

    if r and 'results' in r and 'bindings' in r['results']:
        common_supers = []
        for binding in r['results']['bindings']:
            if 'super' in binding and binding['super']['type'] == 'uri':
                common_supers.append(binding['super']['value'])
        return common_supers
    else:
        raise SparqlException('Malformed response')

def has_type(iri, type_iri, endpoint = DEFAULT_SPARQL_ENDPOINT):
    """
    Queries the SPARQL endpoint if a class is a subclass of a given type.
    @param iri: The IRI of the first class/resource.
    @type iri: str
    @param type_iri: The IRI of the type to check for.
    @type type_iri str
    @type endpoint str
    @param endpoint URL of the SPARQL endpoint to query.
    @rtype list
    @return Returns True iff iri is a subclass of type_iri.
    """
    q = 'PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>\
         PREFIX owl: <http://www.w3.org/2002/07/owl#>\
         ASK { \
              <' + iri + '> rdfs:subClassOf+ <' + type_iri + '> . \
         }'

    try:
        r = __query(q, endpoint)
    except ValueError:
        raise SparqlException('Malformed query %s' % q)

    if 'boolean' in r:
        return r['boolean']
    else:
        raise SparqlException('Malformed response')