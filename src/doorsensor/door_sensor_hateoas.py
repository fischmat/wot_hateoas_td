import json
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from os import curdir, sep

import time

# set GPIO Pins
GPIO_TRIGGER = 18
GPIO_ECHO = 24

# network stuff
PORT_NUMBER = 8080
BASE_URL = 'http://192.168.42.100:%d' % PORT_NUMBER

# Tolerance of distance measurements in cm:
DISTANCE_EPSILON = 1.0
# Time in seconds after which measured distance values are considered correct:
DISTANCE_CALIBRATION_TIME = 5

# Unix-timestamp of the last recognized door opening:
last_door_open_time = 0

# Unix-timestamp of the last recognized door closing:
last_door_close_time = 1 # Set higher than open time, because we assume door is closed at the beginning

import RPi.GPIO as GPIO
# GPIO Mode (BOARD / BCM)
GPIO.setmode(GPIO.BCM)

# set GPIO direction (IN / OUT)
GPIO.setup(GPIO_TRIGGER, GPIO.OUT)
GPIO.setup(GPIO_ECHO, GPIO.IN)


def observe_door_status():
    # Log the timestamp when starting to measure. Marks begin of calibration time.
    start_time = time.time()
    # The distance in cm measured during the last cycle:
    last_distance = 0

    while True:
        # set Trigger to HIGH
        GPIO.output(GPIO_TRIGGER, True)

        # set Trigger after 0.01ms to LOW
        time.sleep(0.00001)
        GPIO.output(GPIO_TRIGGER, False)

        start_time = time.time()
        stop_time = time.time()

        # save StartTime
        while GPIO.input(GPIO_ECHO) == 0:
            start_time = time.time()

        # save time of arrival
        while GPIO.input(GPIO_ECHO) == 1:
            stop_time = time.time()

        # time difference between start and arrival
        time_elapsed = stop_time - start_time
        # multiply with the sonic speed (34300 cm/s)
        # and divide by 2, because there and back
        distance = (time_elapsed * 34300) / 2

        # Check whether this is still in the calibration interval:
        now = time.time()
        in_calibration = now - start_time < DISTANCE_CALIBRATION_TIME

        # If distance is diminished since last measurement, assume the door opened.
        # Omit setting the door open time during calibration phase, so no false positives occure
        if not in_calibration and distance < last_distance - DISTANCE_EPSILON:
            global last_door_open_time
            last_door_open_time = now

        # If distance is increased since last measurement, assume the door opened. Omit in calibration phase again.
        if not in_calibration and distance > last_distance + DISTANCE_EPSILON:
            global last_door_close_time
            last_door_close_time = now

        # Log the distance measured in this cycle:
        last_distance = distance
        # Wait some time until next measurement
        time.sleep(0.5)


# Handles HTTP requests done
class DoorHATEOASRequestHandler(BaseHTTPRequestHandler):

    open_event_signalized = {}

    # Handler for the GET requests
    def do_GET(self):
        if not self.path or self.path == "/":
            # Send the thing description:
            self.send_response(200)
            self.send_header('Content-Type', 'application/door+json')
            self.end_headers()

            self.wfile.write(json.dumps({
                '_links': {
                    'open': {
                        'href': '/open',
                        'type': 'application/door-open-state+json'
                    }
                },
                'name': 'Door protecting some precious goods.',
                'vendor': 'WoT Experts Group'
            }).encode())

        elif self.path == '/open':
            self.send_response(200)
            self.send_header('Content-Type', 'application/door-open-state+json')
            self.end_headers()

            # Door is currently open iff last opening is younger than last closing:
            global last_door_open_time, last_door_close_time
            is_open = last_door_open_time > last_door_close_time
            self.wfile.write(json.dumps({
                'is_open': is_open,
                'last_opened': last_door_open_time,
                'last_closed': last_door_close_time
            }).encode())

        else:
            self.send_response_only(404) # Send Not Found

    def do_POST(self):
        self.send_response_only(405)  # Send Method Not Allowed

    def do_PUT(self):
        self.send_response_only(405)  # Send Method Not Allowed

    def do_DELETE(self):
        self.send_response_only(405)  # Send Method Not Allowed


# Start daemon thread montoring the time of the last door opening:
door_sensor_thread = threading.Thread(target=observe_door_status, args=())
door_sensor_thread.daemon = True
door_sensor_thread.start()

try:
    # Create a web server and define the handler to manage the
    # incoming request
    server = HTTPServer(('', PORT_NUMBER), DoorHATEOASRequestHandler)
    print('Started httpserver on port %d with HATEOAS approach' % PORT_NUMBER)

    # Wait forever for incoming htto requests
    server.serve_forever()

except KeyboardInterrupt:
    print('^C received, shutting down the web server')
    server.socket.close()
