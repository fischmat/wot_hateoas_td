import json
import http.client as httplib
from urllib.parse import urlparse
import datetime

import time

from src import sparql
from src.failuredetection import PingFailureDetector
from src.netscan import HostListScanner
from src.semantics import TDInputBuilder, UnknownSemanticsException
from src.td import ThingDescription

# Configuration. Location of the different things:
ROOM_LIGHT_URL = ''
SPEAKER_URL = ''
DOOR_URL = ''
AUTHENTICATOR_URL = ''

auth_alt_fd = None


class AlarmSystem(object):
    door = None
    authenticator = None
    alarm_source = None

    auth_ttl_secs = 20

    alarm_duration_secs = 30

    last_auth_time = datetime.datetime(1970, 1, 1, 0, 0, 0)

    def on_door_opened(self, is_opened):
        if is_opened:  # If the door is opened and not closed
            # Calculate seconds since last authentication:
            secs = (datetime.datetime.now() - self.last_auth_time).total_seconds()

            if secs <= self.auth_ttl_secs:  # Permission case
                welcome_action = self.alarm_source.get_action_by_types(['http://www.matthias-fisch.de/ontologies/wot#PlaybackAction'])
                if welcome_action:
                    pb = TDInputBuilder()
                    pb.add_option_rule('http://www.matthias-fisch.de/ontologies/wot#SoundFile', 'http://www.matthias-fisch.de/ontologies/wot#WelcomeSound')

                    try:
                        params = pb.build(welcome_action)
                    except UnknownSemanticsException:
                        print("Wanted to say 'Welcome', but semantics of playback action could not be determined :(")
                        return
                    welcome_action.invoke(params)
                else:
                    print("Wanted to say 'Welcome', but alarm device is not capable of that :(")

            else:  # Alarm case
                alarm_action = self.alarm_source.get_action_by_types(
                    ['http://www.matthias-fisch.de/ontologies/wot#AlarmAction'])

                pb = TDInputBuilder()
                pb.add_value_rule('http://www.matthias-fisch.de/ontologies/wot#Duration',
                                       'http://dbpedia.org/resource/Second', self.alarm_duration_secs)
                pb.add_value_rule('http://www.matthias-fisch.de/ontologies/wot#Duration',
                                       'http://dbpedia.org/resource/Millisecond', self.alarm_duration_secs * 1000)
                pb.add_option_rule('http://dbpedia.org/ontology/Colour', 'http://dbpedia.org/resource/Red')

                try:
                    params = pb.build(alarm_action)
                except UnknownSemanticsException as e:
                    print("Cannot determine semantics of alarm actions input type.")
                    return

                alarm_action.invoke(params)

    def on_authentication(self, data):
        self.last_auth_time = datetime.datetime.strptime(data['time'], "%d-%m-%Y %H:%M:%S")
        print("Entry authenticated at %s for %d seconds..." % (self.last_auth_time.strftime("%d-%m-%Y %H:%M:%S"), self.auth_ttl_secs))


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


def on_speaker_failure(fd):
    # Stop old FD on the failed device:
    speaker_fd.invalidate()

    # Remove the offline alarm source:
    alarm_system.alarm_source = None

    alternatives = netscan.scan()  # Scan for hosts that are still up
    for host in alternatives:
        url = "http://%s/" % host
        thing = get_td(url)

        # Find a replacement for the alarm source
        if thing.has_all_events_of(['http://www.matthias-fisch.de/ontologies/wot#AlarmAction']):
            alarm_system.alarm_source = thing

    if alarm_system.alarm_source is None:
        print("WARNING!!! There is no thing for alarming!")


def on_auth_failure(fd):
    # Stop old subscription to event:
    auth_subscription.invalidate()
    # Stop old FD on the failed device:
    auth_fd.invalidate()

    alternatives = netscan.scan()  # Scan for hosts that are still up
    for host in alternatives:
        url = "http://%s/" % host
        thing = get_td(url)

        # Replacement must be capable of the permission event:
        if thing.has_all_events_of(['http://www.matthias-fisch.de/ontologies/wot#DoorEntryPermission']):
            # This is the new authenticator:
            alarm_system.authenticator = thing

            # Subscribe to the event of the new thing
            new_auth_event = thing.get_event_by_types(
                ['http://www.matthias-fisch.de/ontologies/wot#DoorEntryPermission'])
            new_auth_subscription = new_auth_event.subscribe()
            new_auth_subscription.start(callback=alarm_system.on_authentication)

            # Install a new failure detector in case that this thing also fails:
            new_auth_fd = PingFailureDetector(netloc=urlparse(url).netloc, failure_callback=on_auth_failure)
            new_auth_fd.start()


def on_door_failure(fd):
    # Stop old subscription to the doors event:
    door_open_subscription.invalidate()
    # Stop old FD on the failed device:
    door_fd.invalidate()

    alternatives = netscan.scan()  # Scan for hosts that are still up
    for host in alternatives:
        url = "http://%s/" % host
        thing = get_td(url)

        # Replacement must be capable of the door opened event:
        if thing.has_all_events_of(['http://www.matthias-fisch.de/ontologies/wot#DoorOpenEvent']):
            # This is the new door:
            alarm_system.door = thing

            # Subscribe to the event of the new thing
            new_open_event = thing.get_event_by_types(['http://www.matthias-fisch.de/ontologies/wot#DoorOpenEvent'])
            new_door_subscription = new_open_event.subscribe()
            new_door_subscription.start(callback=alarm_system.on_door_opened)

            # Install a new failure detector in case that this thing also fails:
            new_door_fd = PingFailureDetector(netloc=urlparse(url).netloc, failure_callback=on_door_failure)
            new_door_fd.start()


alarm_system = AlarmSystem()
alarm_system.alarm_source = get_td(SPEAKER_URL)
alarm_system.authenticator = get_td(AUTHENTICATOR_URL)
alarm_system.door = get_td(DOOR_URL)

netscan = HostListScanner(['localhost'])

# Validate speaker is what we actually want:
if not alarm_system.alarm_source.has_all_actions_of(['http://www.matthias-fisch.de/ontologies/wot#AlarmAction']):
    print("Speaker at %s does not support required capabilities!" % SPEAKER_URL)
    quit()

if not alarm_system.authenticator.has_all_events_of(
        ['http://www.matthias-fisch.de/ontologies/wot#DoorEntryPermission']):
    print("Authenticator at %s does not support required capabilities!" % AUTHENTICATOR_URL)
    quit()

if not alarm_system.door.has_all_events_of(['http://www.matthias-fisch.de/ontologies/wot#DoorOpenEvent']):
    print("Door at %s does not support required capabilities!" % DOOR_URL)
    quit()

# Subscribe to events:
door_open_event = alarm_system.door.get_event_by_types(['http://www.matthias-fisch.de/ontologies/wot#DoorOpenEvent'])
door_open_subscription = door_open_event.subscribe()
door_open_subscription.start(callback=alarm_system.on_door_opened)

auth_event = alarm_system.authenticator.get_event_by_types(
    ['http://www.matthias-fisch.de/ontologies/wot#DoorEntryPermission'])
auth_subscription = auth_event.subscribe()
auth_subscription.start(callback=alarm_system.on_authentication)

# Register failure detection for things:
speaker_fd = PingFailureDetector(netloc=urlparse(SPEAKER_URL).netloc, failure_callback=on_speaker_failure)
auth_fd = PingFailureDetector(netloc=urlparse(AUTHENTICATOR_URL).netloc, failure_callback=on_auth_failure)
door_fd = PingFailureDetector(netloc=urlparse(DOOR_URL).netloc, failure_callback=on_door_failure)

speaker_fd.start()
auth_fd.start()
door_fd.start()

try:
    while True:
        time.sleep(1)


except KeyboardInterrupt:
    print("Received keyboard interrupt. Exiting...")
