import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from operator import itemgetter
from urllib.parse import urlparse
import http.client as httplib

from src.failuredetection import PingFailureDetector


class NotFoundException(Exception):
    """
    Raised when a resource is not found.
    """
    pass

class MethodNotAllowedException(Exception):
    """
    Raised when the method of a request is not allowed.
    """
    pass

class UnsupportedMediaTypeException(Exception):
    """
    Raised when an unsupported media type is provided.
    """
    pass

class VirtualMapperResource(object):
    """
    Abstract base class for mapping media types.
    """
    _mapped_url = None
    _accept_media_type = None

    def __init__(self, response_media_type, mapped_url):
        """
        :param response_media_type The media type of '/'
        :param mapped_url The URL of the thing being mapped.
        """
        self._response_media_type = response_media_type
        self._mapped_url = mapped_url

    def _fetch_resource(self, url, method="GET", body=None):
        if body and not isinstance(body, str):
            seralized_body = json.dumps(body)
            headers = {'Content-Type': 'application/json'}
        elif isinstance(body, str):
            seralized_body = body
            headers = {'Content-Type': 'text/plain'}
        else:
            serialized_body = None
            headers = {}

        url_parsed = urlparse(url)
        conn = httplib.HTTPConnection(url_parsed.netloc)
        conn.request(method, url_parsed.path, body=serialized_body, headers=headers)
        response = conn.getresponse()

        if response.code == 200:
            # Decode JSON responses. Also treat as JSON if no media type specified:
            if 'Content-Type' not in response.headers or response.headers['Content-Type'].endswith('json'):
                return json.loads(response.read().decode('utf-8'))
            else:
                raise ValueError(
                    'The resource %s is encoded in unknown media type %s' % (url, response.headers['Content-Type']))
        else:
            raise Exception("Received %d %s requesting %s" % (response.code, response.status, url))

    def handle_GET(self, path, headers):
        raise NotImplementedError("Call to abstract method handle_GET(). Instances must implement this method!")

    def handle_POST(self, path, data, headers):
        raise NotImplementedError("Call to abstract method handle_POST(). Instances must implement this method!")

    def accept_media_type(self, href):
        raise NotImplementedError("Call to abstract method accept_media_type(). Instances must implement this method!")

    def mapped_url(self):
        return self._mapped_url

    def response_media_type(self):
        return self._response_media_type


class HATEOASDispatcherService(object):

    _mappers = {}

    _priorities = {}

    def _next_vresource_href(self):
        return "/vr_%d" % len(self._mappers)

    def register_mapper_resource(self, r, priority=0):
        """
        Adds a virtual mapper resource to the dispatcher.
        If there is already a resource registered for the input mediatype/url
        combination then it will be overwritten.
        :param r: The resource to add. Must implement VirtualMapperResource
        :param priority: The priority of this virtual resource. If there is another resource with higher priority
        accepting the same media type, then this resource will not be visible in the bulletin board.
        """
        if isinstance(r, VirtualMapperResource):
            vr_href = self._next_vresource_href()
            self._mappers[vr_href] = r
            self._priorities[vr_href] = priority

            target_parsed = urlparse(r.mapped_url())
            fd = PingFailureDetector(target_parsed.netloc,
                                     failure_callback=(lambda fd: self.on_virtual_resource_target_failed(fd, vr_href, r)),
                                     restart_callback=(lambda fd: self.on_virtual_resource_target_restart(fd, vr_href, r)))
            fd.start()
        else:
            raise ValueError("Mappers must implement VirtualMapperResource")

    def on_virtual_resource_target_failed(self, fd, vr_href, vr):
        del self._mappers[vr_href] # Remove from list of mappers
        num_fallbacks = len([r for r in self._mappers.values() if r.response_media_type() == vr.response_media_type()])
        print("Mapped target %s failed. %d fallback(s) left." % (vr.mapped_url(), num_fallbacks))

    def on_virtual_resource_target_restart(self, fd, vr_href, vr):
        print("Mapped target %s restarted with priority %d" % (vr.mapped_url(), self._priorities[vr_href]))
        self._mappers[vr_href] = vr

    def _get_request_handler(self, base_url, virtual_resources, priorities):
        class HATEOASDispatchServiceHandler(BaseHTTPRequestHandler):
            _virtual_resources = {}
            _base_url = ''
            _priorities = {}

            def __init__(self, *args, **kwargs):
                self._virtual_resources = virtual_resources
                self._base_url = base_url
                self._priorities = priorities
                super(HATEOASDispatchServiceHandler, self).__init__(*args, **kwargs)

            def do_GET(self):
                path_splits = self.path.split('/')

                if self.path == '/':
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/bulletin-board+json')
                    self.end_headers()

                    items = []
                    priorizations = []
                    for vr_path, vr in self._virtual_resources.items():
                        priorizations.append((vr_path, vr, self._priorities[vr_path]))
                    priorizations = sorted(priorizations, key=itemgetter(2), reverse=True)

                    seen_media_types = []
                    priorized_vrs = []
                    for vr_path, vr, vr_prio in priorizations:
                        media_type = vr.response_media_type()
                        if media_type not in seen_media_types:
                            priorized_vrs.append((vr_path, vr))
                            seen_media_types.append(media_type)

                    for vr_path, vr in priorized_vrs:
                        base_url = self._base_url if self._base_url[-1] != '/' else self._base_url[:-1]
                        try:
                            item = json.loads(vr.handle_GET('/', {}))
                            item['_base'] = base_url + vr_path
                            items.append(item)
                        except Exception as e:
                            print(e)
                            pass

                    self.wfile.write(bytes(json.dumps({
                        '_embedded': items
                    }), 'UTF-8'))

                elif len(path_splits) >= 2 and '/' + path_splits[1] in self._virtual_resources.keys():
                    mapper = self._virtual_resources['/' + path_splits[1]]
                    try:
                        href = '/'.join(path_splits[2:]) if len(path_splits) >= 3 else '/'
                        response = mapper.handle_GET(href, self.headers)
                    except NotFoundException:
                        self.send_response_only(404)
                        return
                    except UnsupportedMediaTypeException:
                        self.send_response_only(415)
                        return
                    except MethodNotAllowedException:
                        self.send_response_only(405)
                        return
                    except Exception:
                        self.send_response_only(500)
                        return

                    self.send_response(200)
                    self.send_header('Content-Type', mapper.response_media_type())
                    self.end_headers()

                    self.wfile.write(bytes(response, 'UTF-8'))

                else:
                    self.send_response_only(404)

            def do_POST(self):
                path_splits = self.path.split('/')

                if len(path_splits) >= 2 and '/' + path_splits[1] in self._virtual_resources.keys():
                    mapper = self._virtual_resources['/' + path_splits[1]]
                    href = '/' + '/'.join(path_splits[2:]) if len(path_splits) >= 3 else '/'
                    if self.headers['Content-Type'] == mapper.accept_media_type(href):
                        data = self.rfile.read(int(self.headers['Content-Length'])).decode('utf-8')
                        try:
                            response = mapper.handle_POST(href, data, self.headers)
                        except Exception:
                            self.send_response_only(500)
                            return
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()

                        self.wfile.write(bytes(response, 'UTF-8'))
                    else:
                        self.send_response_only(415) # Send Unsupported Media Type


        return HATEOASDispatchServiceHandler

    def start(self, base_url, port=8080):

        try:
            # Create a web server and define the handler to manage the
            # incoming request
            handler = self._get_request_handler(base_url, self._mappers, self._priorities)
            server = HTTPServer(('', port), handler)
            print('Started httpserver on port ', port)

            # Wait forever for incoming htto requests
            server.serve_forever()

        except KeyboardInterrupt:
            print('^C received, shutting down the web server')
            server.socket.close()