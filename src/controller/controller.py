import json
import http.client as httplib
from urllib.parse import urlparse

import time

from src.td import ThingDescription


# Configuration. Location of the different things:
ROOM_LIGHT_URL = ''
SPEAKER_URL = ''
DOOR_URL = ''
AUTHENTICATOR_URL = ''


def get_td(url):
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

def on_door_opened():
    pass

def on_authentication(data):
    pass

speaker = get_td(SPEAKER_URL)
authenticator = get_td(AUTHENTICATOR_URL)
door = get_td(DOOR_URL)

# Validate speaker is what we actually want:
if not speaker.has_all_actions_of(['http://www.matthias-fisch.de/ontologies/wot#PlaybackAction',
                                   'http://www.matthias-fisch.de/ontologies/wot#AlarmAction']):
    print("Speaker at %s does not support required capabilities!" % SPEAKER_URL)
    quit()

if not authenticator.has_all_events_of(['http://www.matthias-fisch.de/ontologies/wot#DoorEntryPermission']):
    print("Authenticator at %s does not support required capabilities!" % AUTHENTICATOR_URL)
    quit()

if not door.has_all_events_of(['http://www.matthias-fisch.de/ontologies/wot#DoorOpenEvent']):
    print("Door at %s does not support required capabilities!" % DOOR_URL)
    quit()

# Subscribe to events:
door_open_event = door.get_event_by_types(['http://www.matthias-fisch.de/ontologies/wot#DoorOpenEvent'])
door_open_subscription = door_open_event.subscribe(callback=on_door_opened)

auth_event = door.get_event_by_types(['http://www.matthias-fisch.de/ontologies/wot#DoorEntryPermission'])
auth_subscription = auth_event.subscribe(callback=on_authentication)

try:
    while True:
        time.sleep(1)


except KeyboardInterrupt:
    print("Received keyboard interrupt. Exiting...")
