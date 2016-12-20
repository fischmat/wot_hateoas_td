#!flask/bin/python
from flask import Flask, jsonify, make_response, request, abort
import time
from _thread import start_new_thread
import hateoas

app = Flask(__name__)

class DoorDistanceSensor:
    '''
    Door Distance Sensor:
    TODO: implement handler for ultrasonic distance sensor
    '''
    def __init__(self):
        self.door_opened = False
        # Assemble thing description
        door_open_link = hateoas.LinkObject('open-status', '/opened', 'application/door-status+json')
        self.resource_object = hateoas.ResourceObject('/hateoas/door-control', [door_open_link], [], [])

    def open_door(self):
        self.door_opened = True

        def close_after_timeout(timeout):
            time.sleep(timeout)
            self.door_opened = False

        start_new_thread(close_after_timeout, (5))


# Initialization.
door_distance_sensor = DoorDistanceSensor()

# URL routes.
@app.route('/hateoas/door-control', methods=['GET'])
def description():
    return door_distance_sensor.resource_object.to_json()


@app.route('/hateoas/door-control/opened', methods=['GET'])
def door_opened():
    return jsonify({"door_open": door_distance_sensor.door_opened})


@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)


if __name__ == '__main__':
    app.run(debug=True)
