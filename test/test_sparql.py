from unittest import TestCase

from src import sparql
from src.sparql import SPARQLNamespaceRepository, UnknownPrefixException


class Test_Sparql(TestCase):
    def test_equivalent_classes(self):
        self.assertEqual(sparql.equivalent_classes('http://purl.org/iot/vocab/m3-lite#Thermometer'),
                         ['http://purl.oclc.org/NET/ssnx/meteo/aws#TemperatureSensor',
                          'http://casas.wsu.edu/owl/cose.owl#TempuratureSensor'])

        self.assertEqual(sparql.equivalent_classes('http://example.org/bla#NotExisting'), [])

    def test_classes_equivalent(self):
        self.assertTrue(sparql.classes_equivalent('http://purl.org/iot/vocab/m3-lite#Thermometer', 'http://purl.oclc.org/NET/ssnx/meteo/aws#TemperatureSensor'))
        self.assertFalse(sparql.classes_equivalent('http://purl.org/iot/vocab/m3-lite#Thermometer', 'http://elite.polito.it/ontologies/dogont.owl#DeepFreezer'))

    def test_namespace_repository(self):
        ns = SPARQLNamespaceRepository()
        ns.register('dogont', 'http://elite.polito.it/ontologies/dogont.owl#')
        self.assertEqual(ns.resolve('dogont:Lighting'), 'http://elite.polito.it/ontologies/dogont.owl#Lighting')
        self.assertEqual(ns.resolve('http://elite.polito.it/ontologies/dogont.owl#Lighting'), 'http://elite.polito.it/ontologies/dogont.owl#Lighting')

        with self.assertRaises(UnknownPrefixException):
            ns.resolve('unknownont:Lighting')

        with self.assertRaises(ValueError):
            ns.resolve('nonshorthandgibberish')