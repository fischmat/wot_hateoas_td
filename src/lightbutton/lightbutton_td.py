import json
from _thread import start_new_thread
from sys import argv, stderr
from urllib.parse import urlparse

import http.client as httplib
import RPi.GPIO as GPIO # TODO Uncomment on RPi
import time

from src import td
from src.td import ThingDescription

known_light_classes = [
    'http://elite.polito.it/ontologies/dogont.owl#Lighting'
]

class MalformedResponse(Exception):
    """
    Signalizes that the response received from a server is not formed as expected.
    """
    pass

class UnsupportedProtocol(Exception):
    """
    Signalizes that another protocol than HTTP is required for communication with a thing.
    """
    pass

def check_button_status(on_press, button_gpio):
    """
    Periodically checks whether the attached button was pressed and calls on_press in such an case.
    @type on_press callable
    @param on_press Function that is invoked once per button press in a new thread.
    @type button_gpio int
    @param button_gpio Number of the gpio the button is connected to.
    """

    GPIO.setmode(GPIO.BCM)
    GPIO.setup(button_gpio, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    # We want only fire an event once per button press, so use flag to remember its state:
    isButtonPressed = False

    while True:
        input_state = GPIO.input(button_gpio)
        if input_state == False and not isButtonPressed:
            start_new_thread(on_press, ())  # Start function in new thread
            isButtonPressed = True  # Prevent repeated calls per button press
            time.sleep(0.2)
        else:
            isButtonPressed = False

def toggle_light_state(onoff_prop):
    # Get the current value of the light.
    # dogont:OnOffState states that this is either 'on' or 'off'
    light_state = onoff_prop.value()
    # Switch state and set the new value:
    if light_state == 'on':
        onoff_prop.set('off')
    else:
        onoff_prop.set('on')


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

# Help
if len(argv) == 1 or '--help' in argv: # If no arguments passed via CLI. (Interpreter path is always in there)
    print("Room Light switch implementing HATEOAS approach.")
    print("Options:")
    print("--light-url URL : Specifies the URL of the light TD.")
    print("--button-gpio GPIO: Specifies the GPIO number of the button.")
    quit()

# Validate and process CLI arguments:
if '--light-url' not in argv or argv.index('--light-url') >= len(argv) - 1:
    stderr.write("Missing required option '--light-url'\n")
    quit()
else:
    light_url = argv[argv.index('--light-url') + 1]

if '--button-gpio' not in argv or argv.index('--button-gpio') >= len(argv) - 1:
    stderr.write("Missing required option '--button-gpio'\n")
    quit()
else:
    button_gpio = argv[argv.index('--button-gpio') + 1]

if '--port' not in argv or argv.index('--port') < len(argv) - 1:
    port = 80
else:
    port = int(argv[argv.index('--port') + 1])

light_td = get_td(light_url) # Get the thing description at the specified location

# Get the property of the TD that is equivalent to our known On/Off type:
onoff_prop = light_td.get_property_by_types(['http://elite.polito.it/ontologies/dogont.owl#OnOffState'])

if not onoff_prop:
    stderr.write("Thing has no appropriate property for On/Off state.")
    quit()

# Start periodical checks on the button status and toggle the on/off status:
check_button_status(toggle_light_state(onoff_prop), button_gpio)