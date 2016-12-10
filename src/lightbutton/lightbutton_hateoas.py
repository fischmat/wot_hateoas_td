import json
from sys import argv, stderr

import time
from urllib.parse import urlparse

import RPi.GPIO as GPIO
from _thread import start_new_thread
import http.client as httplib

# Defines which media types of lights are accepted by the thing:
supported_light_mediatypes = [
    'application/roomlight+json'
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
            start_new_thread(on_press, ()) # Start function in new thread
            isButtonPressed = True # Prevent repeated calls per button press
            time.sleep(0.2)
        else:
            isButtonPressed = False

def get_media_type(http_response):
    """
    Returns the Content-Type header field of a HTTP response.
    @type http_response http.client.HTTPResponse
    @param http_response Response from a HTTP request.
    @rtype str
    @return The media type of the responses payload or None if not provided in the response headers.
    """
    for header_name, header_value in http_response.getheaders():
        if header_name == 'content-type':
            return header_value
    return None

def dispatch_bulletin_board(bulletin):
    """
    Checks a bulletin board for a light resource.
    @type bulletin dict|str
    @param bulletin The bulletin board as json string or as a dictionary.
    @rtype dict|None
    @return (base, media_type) or None if no appropriate light was found.
    The first is the base of the light as unserialized JSON, the second is the media type of the lights base.
    @raise UnsupportedProtocol If the bulletin board directs to a non-HTTP URL.
    @raise MalformedResponse If the bulletin board is malformed.
    """
    if isinstance(bulletin, str):
        bulletin = json.loads(bulletin)

    if '_embedded' in bulletin.keys() and 'item' in bulletin['_embedded'].keys():
        for item in bulletin['_embedded']['item']:
            # Parse the base address of the thing:
            thing_root = urlparse(item['_base'])

            # Check if the thing uses HTTP:
            if thing_root.scheme != 'http':
                raise UnsupportedProtocol("Protocol %s required for discovery of %s is unsupported." % (thing_root.scheme, item['_base']))

            # Get the port we use for communication:
            if thing_root.port:
                port = thing_root.port
            else:
                port = 80

            conn = httplib.HTTPConnection(thing_root.host, port=port)
            conn.request('GET', thing_root.path)
            response = conn.getresponse()
            media_type = get_media_type(response)
            if media_type in supported_light_mediatypes:
                data = response.read()
                conn.close()
                return (json.loads(data), media_type)

        return None

    else:
        raise MalformedResponse('Bulletin board either missing _embedded or item entry.')


def get_light_description(host, port=80):
    """
    Retrieves the base of the light on host. A light is accepted if its base media type is listed in supported_light_mediatypes.
    Automatically follows bulletin boards if multiple devices are hosted on host.
    @type host str
    @param host The name of the host where the light thing is hosted.
    @type port int
    @param port The port where the HTTP server listens on host.
    @rtype dict|None
    @return Tuple (base, media_type) or None if no appropriate light was found.
    The first is the base of the light as unserialized JSON, the second is the media type of the lights base.
    """
    conn = httplib.HTTPConnection(host, port=port)
    conn.request('GET', '/')
    response = conn.getresponse()

    media_type = get_media_type(response)
    if media_type == 'application/bulletin-board+json': # Does this device host multiple things?
        light = dispatch_bulletin_board(response.read())
        conn.close()
        return light

    elif media_type in supported_light_mediatypes:
        light = json.loads(response.read())
        conn.close()
        return (light, media_type)

    else:
        return None


if len(argv) == 1: # If no arguments passed via CLI. (Interpreter path is always in there)
    print("Room Light switch implementing HATEOAS approach.")
    print("Options:")
    print("--light-host ADDR : Specifies the hostname of a light or its IPv4 address.")
    print("--button-gpio GPIO: Specifies the GPIO number of the button.")

if '--light-host' not in argv or argv.index('--light-host') < len(argv) - 1:
    stderr.write("Missing required option '--light-host'\n")
    quit()
else:
    light_host = argv[argv.index('--light-host') + 1]

if '--button-gpio' not in argv or argv.index('--button-gpio') < len(argv) - 1:
    stderr.write("Missing required option '--button-gpio'\n")
    quit()
else:
    button_gpio = argv[argv.index('--button-gpio') + 1]

if '--port' not in argv or argv.index('--port') < len(argv) - 1:
    port = 80
else:
    port = int(argv[argv.index('--port') + 1])

# Get the description of the light:
light = get_light_description(light_host, port)
if not light:
    stderr.write("No light found :(\n")

