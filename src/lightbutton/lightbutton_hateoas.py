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

def toggle_light_power_status(light, light_url):
    """
    Toggles the powerstatus of a application/roomlight+json light thing.
    @type light dict
    @param light The base description of a room light.
    @type light_url str
    @param light_url URL of the lights root resource
    @rtype bool
    @return Returns true on success. Prints to stderr and returns False on error.
    @raise MalformedResponse On unexpected structure/values of the responses.
    """
    power_status_resource = light['_links']['onoff']
    href = urlparse(light_url + power_status_resource['href'])

    if href.port:
        port = href.port
    else:
        port = 80

    conn = httplib.HTTPConnection(href.host, port=port)
    conn.request('GET', href.path)
    response = conn.getresponse()
    media_type = get_media_type(response)
    if media_type == 'text/plain':
        power_state = response.read()
    else:
        raise MalformedResponse('Expected media-type text/plain for resource %s. Received %s' % (light_url + power_status_resource['href'], media_type))
    conn.close()

    if power_state == 'on':
        new_power_state = 'off'
    elif power_state == 'off':
        new_power_state = 'on'
    else:
        raise MalformedResponse('Got unknown power state %s' % power_state)

    power_update_resource = light['_forms']['onoff']
    if power_update_resource['accept'] != 'text/plain':
        raise MalformedResponse('Form onoff only supports unknown media type %s' % power_update_resource['accept'])

    href = urlparse(light_url + power_update_resource['href'])
    if href.port:
        port = href.port
    else:
        port = 80

    conn = httplib.HTTPConnection(href.host, port=port)
    conn.request(power_update_resource['method'], href.path, body=new_power_state)
    response =  conn.getresponse()

    if response.code == 200:
        return True
    else:
        stderr.write("%s to %s resulted in %s\n" % (power_update_resource['method'], light_url + power_update_resource['href'], response.code + response.status))
        return False


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
    @return (base, media_type, url) or None if no appropriate light was found.
    The first is the base of the light as unserialized JSON, the second is the media type of the lights base and the third its base URL.
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
                return (json.loads(data), media_type, item['_base'])

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
    @return Tuple (base, media_type, light_url) or None if no appropriate light was found.
    The first is the base of the light as unserialized JSON, the second is the media type of the lights base and the third its base URL.
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
        return (light, media_type, "http://%s:%d/" % (host, port))

    else:
        return (None, None, None)


if len(argv) == 1 or '--help' in argv: # If no arguments passed via CLI. (Interpreter path is always in there)
    print("Room Light switch implementing HATEOAS approach.")
    print("Options:")
    print("--light-host ADDR : Specifies the hostname of a light or its IPv4 address.")
    print("--button-gpio GPIO: Specifies the GPIO number of the button.")
    quit()

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
light, media_type, light_url = get_light_description(light_host, port)
if not light:
    stderr.write("No light found :(\n")
else:
    print("Found light '%s'" % light['name'])

if media_type == 'application/roomlight+json':
    check_button_status(lambda: toggle_light_power_status(light, light_url), button_gpio)
else:
    stderr.write("Don't know how to handle media type %s" % media_type)