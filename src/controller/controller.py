import datetime
import time
from urllib.parse import urlparse

from src.failuredetection import PingFailureDetector
from src.netscan import HostListScanner
from src.semantics import TDInputBuilder, UnknownSemanticsException

# Configuration. Location of the different things:
from src.td import get_thing_description_from_url

ROOM_LIGHT_URL = 'http://192.168.43.153:80/'
SPEAKER_URL = 'http://192.168.43.171:5000/td/speaker'
DOOR_URL = 'http://192.168.42.100:8080/'
AUTHENTICATOR_URL = 'http://192.168.43.171:5000/td/door_control'

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
            print("Door opened!")
            # Calculate seconds since last authentication:
            try:
                auth_prop = self.authenticator.get_property_by_types(['http://www.matthias-fisch.de/ontologies/wot#DoorEntryPermission'])
                authenticated = auth_prop.value()
            except Exception:
                authenticated = False
            secs = (datetime.datetime.now() - self.last_auth_time).total_seconds()

            if authenticated:  # Permission case
                print("Permission")
                welcome_action = self.alarm_source.get_action_by_types(['http://www.matthias-fisch.de/ontologies/wot#PlayWelcomeAction'])
                if welcome_action:
                    ib = TDInputBuilder()
                    ib.add_oneof_rule('http://www.matthias-fisch.de/ontologies/wot#SoundFile', 'http://www.matthias-fisch.de/ontologies/wot#WelcomeSound')

                    try:
                        params = ib.build(welcome_action)
                    except UnknownSemanticsException:
                        print("Wanted to say 'Welcome', but semantics of playback action could not be determined :(")
                        return
                    welcome_action.invoke(params)
                else:
                    print("Wanted to say 'Welcome', but alarm device is not capable of that :(")

            else:  # Alarm case
                print("No Permission")
                alarm_action = self.alarm_source.get_action_by_types(
                    ['http://www.matthias-fisch.de/ontologies/wot#AlarmAction'])

                ib = TDInputBuilder()
                ib.add_value_rule('http://www.matthias-fisch.de/ontologies/wot#Duration',
                                       'http://dbpedia.org/resource/Second', self.alarm_duration_secs)
                ib.add_value_rule('http://www.matthias-fisch.de/ontologies/wot#Duration',
                                       'http://dbpedia.org/resource/Millisecond', self.alarm_duration_secs * 1000)
                ib.add_oneof_rule('http://dbpedia.org/ontology/Colour', 'http://dbpedia.org/resource/Red')

                try:
                    params = ib.build(alarm_action)
                except UnknownSemanticsException as e:
                    print("Cannot determine semantics of alarm actions input type.")
                    return

                alarm_action.invoke(params)

    def on_authentication(self, data):
        self.last_auth_time = datetime.datetime.strptime(data['time'], "%d-%m-%Y %H:%M:%S")
        print("Entry authenticated at %s for %d seconds..." % (self.last_auth_time.strftime("%d-%m-%Y %H:%M:%S"), self.auth_ttl_secs))



def on_speaker_failure(fd):
    print("Speaker failed!")

    # Stop old FD on the failed device:
    speaker_fd.invalidate()

    # Remove the offline alarm source:
    alarm_system.alarm_source = None

    alternatives = netscan.scan()  # Scan for hosts that are still up
    for host in alternatives:
        url = "http://%s/" % host
        try:
            thing = get_thing_description_from_url(url)
        except Exception:
            continue

        # Find a replacement for the alarm source
        if thing.has_all_actions_of(['http://www.matthias-fisch.de/ontologies/wot#AlarmAction']):
            alarm_system.alarm_source = thing

    if alarm_system.alarm_source is None:
        print("WARNING!!! There is no thing for alarming!")


def on_door_failure(fd):
    # Stop old subscription to the doors event:
    door_open_subscription.invalidate()
    # Stop old FD on the failed device:
    door_fd.invalidate()

    alternatives = netscan.scan()  # Scan for hosts that are still up
    for host in alternatives:
        url = "http://%s/" % host
        thing = get_thing_description_from_url(url)

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
alarm_system.alarm_source = get_thing_description_from_url(SPEAKER_URL)
alarm_system.authenticator = get_thing_description_from_url(AUTHENTICATOR_URL)
alarm_system.door = get_thing_description_from_url(DOOR_URL)

netscan = HostListScanner(['192.168.43.153'])

# Validate speaker is what we actually want:
if not alarm_system.alarm_source.has_all_actions_of(['http://www.matthias-fisch.de/ontologies/wot#AlarmAction']):
    print("Speaker at %s does not support required capabilities!" % SPEAKER_URL)
    quit()

if not alarm_system.authenticator.has_all_properties_of(
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

# Register failure detection for things:
speaker_fd = PingFailureDetector(netloc=urlparse(SPEAKER_URL).netloc, failure_callback=on_speaker_failure)
door_fd = PingFailureDetector(netloc=urlparse(DOOR_URL).netloc, failure_callback=on_door_failure)

speaker_fd.start()
door_fd.start()

try:
    while True:
        time.sleep(1)


except KeyboardInterrupt:
    print("Received keyboard interrupt. Exiting...")
