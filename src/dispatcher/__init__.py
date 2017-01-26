import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
import http.client as httplib

PORT_NUMBER = 5678

class MediaTypeTranslator(object):

    def input_type(self):
        raise NotImplementedError("Call to abstract method input_type(). Instances must implement this method!")

    def output_type(self):
        raise NotImplementedError("Call to abstract method output_type(). Instances must implement this method!")

    def translate(self, input, method, body):
        """
        Takes an input of representation described by the mediatype returned by input_type() and translates it to one
        described by output_type().
        :param input: The input of appropriate representation.
        :param method The HTTP method used for accessing the input.
        :return: The translated input in output representation of this translator.
        """
        # TODO Use real calling to URLs here!
        raise NotImplementedError("Call to abstract method translate(). Instances must implement this method!")

class HATEOASDispatchService(object):

    _mapped_urls = []

    # Translators indexed by string 'input-mediatype -> output-mediatype'
    _translators = {}

    def register_url(self, url):
        """
        Adds an URL to the list of dispatched resources.
        Note that currently only HTTP is supported.
        :param url: The url to add.
        """
        parse = urlparse(url)
        if parse.scheme == 'http': # Only HTTP is allowed
            self._mapped_urls.append(url)
        else:
            raise ValueError("Only HTTP is supported. Resource with access scheme %s given." % parse.scheme)

    def register_translator(self, t):
        """
        Adds an translator to the dispatcher. If there is already a translator registered for the input/output mediatype
        combination then it will be overwritten.
        :param t: The translator to add. Must implement MediaTypeTranslator
        """
        if isinstance(t, MediaTypeTranslator):
            key = "%s -> %s" % (t.input_type(), t.output_type())
        else:
            raise ValueError("Translators must implement MediaTypeTranslator interface!")

    def _get_request_handler(self, virtual_resources):
        class HATEOASDispatchServiceHandler(BaseHTTPRequestHandler):
            _virtual_resources = {}

            def __init__(self, *args, **kwargs):
                super(HATEOASDispatchServiceHandler, self).__init__(*args, **kwargs)
                self._virtual_resources = virtual_resources

            def __fetch_resource(self, url, method="GET", body=None):
                if body:
                    seralized_body = json.dumps(body)
                    headers = {'Content-Type': 'application/json'}
                else:
                    serialized_body = None
                    headers = None

                url_parsed = urlparse(url)
                conn = httplib.HTTPConnection(url_parsed.netloc)
                conn.request(method, url_parsed.path, body=serialized_body, headers=headers)
                response = conn.getresponse()

                if response.code == 200:
                    # Decode JSON responses. Also treat as JSON if no media type specified:
                    if 'Content-Type' in response.headers or response.headers['Content-Type'] == 'application/json':
                        return json.loads(response.read().decode('utf-8'))
                    else:
                        raise ValueError('The resource %s is encoded in unknown media type %s' % (url, response.headers['Content-Type']))
                else:
                    raise Exception("Received %d %s requesting %s" % (response.code, response.status, url))

            def do_GET(self):
                if self.path == '/':
                    # TODO Send bulletin board
                    pass

                elif self.path in self._virtual_resources.keys():
                    translator, target_url = self._virtual_resources[self.path]
                    target_resource = self.__fetch_resource(target_url, method='GET')



        return HATEOASDispatchServiceHandler

try:
    # Create a web server and define the handler to manage the
    # incoming request
    server = HTTPServer(('', PORT_NUMBER), myHandler)
    print
    'Started httpserver on port ', PORT_NUMBER

    # Wait forever for incoming htto requests
    server.serve_forever()

except KeyboardInterrupt:
    print
    '^C received, shutting down the web server'
    server.socket.close()