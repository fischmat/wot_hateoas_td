import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from os import curdir, sep

import time

# set GPIO Pins
GPIO_TRIGGER = 18
GPIO_ECHO = 24

# network stuff
PORT_NUMBER = 8080
BASE_URL = 'http://192.168.42.100:%d' % PORT_NUMBER

# import RPi.GPIO as GPIO
# # GPIO Mode (BOARD / BCM)
# GPIO.setmode(GPIO.BCM)
#
# # set GPIO direction (IN / OUT)
# GPIO.setup(GPIO_TRIGGER, GPIO.OUT)
# GPIO.setup(GPIO_ECHO, GPIO.IN)


def distance():
    # # set Trigger to HIGH
    # GPIO.output(GPIO_TRIGGER, True)
    #
    # # set Trigger after 0.01ms to LOW
    # time.sleep(0.00001)
    # GPIO.output(GPIO_TRIGGER, False)
    #
    # StartTime = time.time()
    # StopTime = time.time()
    #
    # # save StartTime
    # while GPIO.input(GPIO_ECHO) == 0:
    #     StartTime = time.time()
    #
    # # save time of arrival
    # while GPIO.input(GPIO_ECHO) == 1:
    #     StopTime = time.time()
    #
    # # time difference between start and arrival
    # TimeElapsed = StopTime - StartTime
    # # multiply with the sonic speed (34300 cm/s)
    # # and divide by 2, because there and back
    # distance = (TimeElapsed * 34300) / 2
    #
    # return distance
    return 4


# This class will handles any incoming request from
# the browser
class DoorTDRequestHandler(BaseHTTPRequestHandler):
    # Handler for the GET requests
    def do_GET(self):
        if not self.path or self.path == "/":
            self.send_response(200)
            self.send_header('Content-Type', 'application/thing-description+json')
            self.end_headers()

            self.wfile.write(json.dumps({
                "@context": [
                    "http://w3c.github.io/wot/w3c-wot-td-context.jsonld",
                    {"m3lite": "http://purl.org/iot/vocab/m3-lite#"}, #Introduce M3 lite vocabulary
                    {"jup": "http://w3id.org/charta77/jup/"},
                    {"dbp": "http://dbpedia.org/property/"}
                ],
                "@type": "m3lite:Door",
                "name": "Door protecting some precious goods.",
                "vendor": "WoT Experts Group",
                "uris": [BASE_URL],
                "encodings": ["JSON"],
                "properties": [
                    {
                        "@type": "saref:OpenCloseState",
                        "valueType": {
                            "type": "boolean",
                            "oneOf": [
                                {
                                    "constant": True,
                                    "saref:OpenCloseState": "dbp:open"
                                },
                                {
                                    "constant": False,
                                    "saref:OpenCloseState": "dbp:closed"
                                }
                            ]
                        },
                        "writeable": False,
                        "hrefs": ["/isopen"],
                        "stability": -1 # Irregular changes
                    }
                ],
                "events": [
                    {
                        "@type": "jup:DoorOpening",
                        "name": "Door opened",
                        "valueType": {
                            "type": "integer",
                            "m3lite:Time": "m3lite:Timestamp"
                        },
                        "hrefs": ["/openevent"]
                    }
                ]
            }).encode())


try:
    # Create a web server and define the handler to manage the
    # incoming request
    server = HTTPServer(('', PORT_NUMBER), DoorTDRequestHandler)
    print('Started httpserver on port ', PORT_NUMBER)

    # Wait forever for incoming htto requests
    server.serve_forever()

except KeyboardInterrupt:
    print('^C received, shutting down the web server')
    server.socket.close()
