# sparql module
# Defines functionality to perform certain queries
# The endpoint used is lov.okfn.org

from requests import post

class SparqlException(Exception):
    """
    Exception to signalize that something went wrong during a query to a SPARQL-endpoint.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


def __query(q):
    """
    Files a query to the SPARQL-endpoint at lov.okfn.org
    @type q: str
    @param q: A SPARQL query.
    @rtype: dict|None
    @return: The response of the endpoint or None on error or malformed query.
    """
    headers = {
        'Accept': 'application/sparql-results+json,*/*;q=0.9',
        'User-Agent': 'WoT TD Resolver'
    }
    r = post('http://lov.okfn.org/dataset/lov/sparql', data={'query': q}, headers=headers)

    if r:
        return r.json()
    else:
        return None


def equivalent_classes(iri):
    """
    Queries the SPARQL-endpoint at lov.okfn.org for classes/resources that are equal to the one given.
    Takes equivalency by the transitive closure of rdfs:seeAlso, owl:sameAs and owl:equivalentClass into account.
    @type iri: str
    @param iri: The IRI of the class for which equivalent classes should be found.
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
        r = __query(q)
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


def classes_equivalent(iri1, iri2):
    """
    Queries the SPARQL-endpoint at lov.okfn.org for equivalency of two classes/resources.
    Takes equivalency by the transitive closure of rdfs:seeAlso, owl:sameAs and owl:equivalentClass into account.
    @type iri1: str
    @param iri1: The IRI of the first class/resource.
    @type iri2: str
    @param iri2: The IRI of the second class/resource.
    @rtype: bool
    @return: Returns true if the classes/resources are equivalent.
    @raise SparqlException: Raised if the internally constructed query is malformed or the response of the endpoint is.
    """
    q = 'PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#> \
        PREFIX owl: <http://www.w3.org/2002/07/owl#> \
        ASK {\
                 { <' + iri1 + '> rdfs:seeAlso+ <' + iri2 + '> .} \
                UNION { <' + iri1 + '> owl:sameAs+ <' + iri2 + '> . } \
                 UNION { <' + iri1 + '> owl:equivalentClass+ <' + iri2 + '> .} \
                UNION { <' + iri2 + '> rdfs:seeAlso+ <' + iri1 + '>.} \
                UNION { <' + iri2 + '> owl:sameAs+ <' + iri1 + '> . } \
                 UNION { <' + iri2 + '> owl:equivalentClass+ <' + iri1 + '> .} \
        }'

    try:
        r = __query(q)
    except ValueError:
        raise SparqlException('Malformed query %s' % q)

    if 'boolean' in r:
        return r['boolean']
    else:
        raise SparqlException('Malformed response')