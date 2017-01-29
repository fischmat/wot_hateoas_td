import json

from src.dispatcher import HATEOASDispatcherService, VirtualMapperResource, NotFoundException, \
    UnsupportedMediaTypeException

class LightAlarmMapper(VirtualMapperResource):

    def __init__(self, mapped_url):
        super().__init__('application/alarm+json', mapped_url)

    def handle_GET(self, path, headers):
        if path == '/':
            light = self._fetch_resource(self.mapped_url(), method='GET')
            response = {
                '_forms': {
                    'alarm': {
                        'href': '/alarm',
                        'method': 'POST',
                        'accept': 'application/alarm-invocation+json'
                    }
                }
            }
            for k, v in light.items():
                if not k.startswith('_'):
                    response[k] = v
            return json.dumps(response)
        else:
            raise NotFoundException("%s does not exist" % path)

    def handle_POST(self, path, data, headers):
        if path == '/alarm':
            light = self._fetch_resource(self.mapped_url(), method='GET')
            if light['_forms']['strobeon']['accept'] == 'application/light-strobe-config+json':
                self._fetch_resource(url=self._urljoin(light['_forms']['strobeon']['href']),
                                     method= light['_forms']['strobeon']['method'],
                                     body={
                                         'duration': json.loads(data)['duration']
                                     },
                                     headers={'Content-Type': 'application/light-strobe-config+json'})
            else:
                raise UnsupportedMediaTypeException()

    def accept_media_type(self, href):
        if href == '/alarm':
            return 'application/alarm-invocation+json'
        else:
            return False

class SpeakerAlarmMapper(VirtualMapperResource):

    def __init__(self, mapped_url):
        super().__init__('application/alarm+json', mapped_url)

    def handle_GET(self, path, headers):
        if path == '/':
            speaker = self._fetch_resource(self.mapped_url(), method='GET')
            response = {
                '_forms': {
                    'alarm': {
                        'href': '/alarm',
                        'method': 'POST',
                        'accept': 'application/alarm-invocation+json'
                    }
                }
            }
            for k, v in speaker.items():
                if not k.startswith('_'):
                    response[k] = v
            return json.dumps(response)
        else:
            raise NotFoundException("%s does not exist" % path)

    def handle_POST(self, path, data, headers):
        if path == '/alarm':
            speaker = self._fetch_resource(self.mapped_url(), method='GET')
            if speaker['_forms']['play_alarm']['accept'] == 'text/plain':
                return self._fetch_resource(url=self._urljoin(speaker['_forms']['play_alarm']['href']),
                                     method= speaker['_forms']['play_alarm']['method'])
            else:
                raise UnsupportedMediaTypeException()

    def accept_media_type(self, href):
        if href == '/alarm':
            return 'application/alarm-invocation+json'
        else:
            return False


dispatcher = HATEOASDispatcherService()
dispatcher.register_mapper_resource(LightAlarmMapper('http://192.168.43.153:80/'))
dispatcher.register_mapper_resource(SpeakerAlarmMapper('http://192.168.43.171:5000/hateoas/speaker'), priority=1) # TODO Change
dispatcher.start('http://192.168.43.226:7894/', 7894)