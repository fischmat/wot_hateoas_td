#!flask/bin/python3
from flask import Flask, jsonify, make_response, request, abort, redirect
import time
# from _thread import start_new_thread
import hateoas
from rfid import *
import pygame
import time

app = Flask(__name__)

alarm_file = "alarm.mp3"
welcome_file = "welcome.mp3"
ring_file = "ring.mp3"


class SpeakerThing:
	def __init__(self):
		play_alarm = hateoas.FormObject('play_alarm', '/play_alarm', hateoas.Method.POST, 'text/plain')
		play_welcome = hateoas.FormObject('play_welcome', '/play_welcome', hateoas.Method.POST,
										  'text/plain')
		play_ring = hateoas.FormObject('play_ring', '/play_ring', hateoas.Method.POST, 'text/plain')
		self.resource_object = hateoas.ResourceObject('/hateoas/speaker', [], [play_alarm, play_welcome, play_ring], [])

	# hateoas.ResourceObject('sounds', )

	def start_alarm(self):
		self.sound(alarm_file)

	def start_welcome(self):
		self.sound(welcome_file)

	def start_ring(self):
		self.sound(ring_file)

	def sound(self, sound_file):
		pygame.mixer.init()
		pygame.mixer.music.load(sound_file)
		pygame.mixer.music.play()
		time.sleep(4)
		pygame.mixer.music.stop()


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

		# RFID handler
		self.rfid_reader = RFIDReader()
		self.rfid_reader.start()

	def __exit__(self, *args):
		self.rfid_reader.stop()
		if self.rfid is not None:
			self.rfid.__exit__(*args)

	def is_door_open(self):
		return self.rfid_reader.is_authenticated()  # Initialization.


door_distance_sensor = DoorDistanceSensor()
speaker = SpeakerThing()


# URL routes.
@app.route('/hateoas/door_control', methods=['GET'])
def description():
	return door_distance_sensor.resource_object.to_json()


@app.route('/hateoas/door_control/opened', methods=['GET'])
def door_opened():
	return jsonify({"door_open": door_distance_sensor.is_door_open()})


@app.route('/td/door_control')
def door_description_td():
	return jsonify({
		"@context": [
			"http://w3c.github.io/wot/w3c-wot-td-context.jsonld",
			{"m3lite": "http://purl.org/iot/vocab/m3-lite#"},
			{"xapi": "http://ns.inria.fr/ludo/v1/xapi"},
			{"cc": "http://creativecommons.org/ns#"}
		],
		"@type": "xapi:Authentication",
		"name": "The concept of verifying the identity of a user or system.",
		"vendor": "WoT Experts Group",
		"uris": ["http://192.168.43.171:5000/td/door_control"],
		"encodings": ["JSON"],
		"properties": [
			{
				"@type": "cc:Permission",
				"valueType": {
					"type": "boolean",
				},
				"writeable": False,
				"hrefs": ["/isauthenticated"],
				"stability": -1
			}
		],
		"events": [
			{
				"@type": "cc:Permission",
				"name": "Authenticated successfully",
				"valueType": {
					"type": "boolean",
					"m3lite:Time": "m3lite:TimeStamp"
				},
				"hrefs": ["/authenticatedevent"]
			}
		]
	})


@app.route('/td/door_control/isauthenticated')
def door_control_td_isauthenticated():
	return jsonify({"value": door_distance_sensor.is_door_open()})


@app.route('/td/door_control/authenticatedevent')
def door_control_td_authenticatedevent():
	return redirect("http://192.168.43.171:5000/td/door_control/isauthenticated", code=308)
	#return make_response(jsonify({"timestamp": door_distance_sensor.is_door_open()}), 308)


@app.route('/hateoas/speaker', methods=['GET'])
def speaker_description():
	return speaker.resource_object.to_json()


@app.route('/hateoas/speaker/play_alarm', methods=['POST'])
def play_alarm():
	speaker.start_alarm()
	return make_response(jsonify({"Playing": "OK"}), 200)


@app.route('/hateoas/speaker/play_welcome', methods=['POST'])
def play_welcome():
	speaker.start_welcome()
	return make_response(jsonify({"Playing": "OK"}), 200)


@app.route('/hateoas/speaker/play_ring', methods=['POST'])
def play_ring_hateoas():
	speaker.start_ring()
	return make_response(jsonify({"Playing": "OK"}), 200)


@app.route('/hateoas/speaker/sounds', methods=['GET'])
def list_sounds():
	return jsonify(["alarm", "welcome"])


@app.route('/td/speaker')
def speaker_description_td():
	return jsonify({
		"@context": [
			"http://w3c.github.io/wot/w3c-wot-td-context.jsonld",
			{"mf": "http://www.matthias-fisch.de/ontologies/wot#"},
			{"ncal":"http://www.semanticdesktop.org/ontologies/2007/04/02/ncal#"}
		],
		"@type": "mf:Speaker",
		"name": "Speaker",
		"vendor": "WoT Experts Group",
		"uris": ["http://192.168.43.171:5000/td/speaker"],
		"encodings": ["JSON"],
		"properties": [],
		"actions": [
			{
				"@type": "mf:PlayWelcomeAction",
				"name": "Play welcome sound",
				"inputData": {},
				"hrefs": ["/play_welcome"]
			},
			{
				"@type": "mf:BellRingAction",
				"name": "Play doorbell ring sound",
				"inputData": {},
				"hrefs": ["/play_ring"]
			},
			{
				"@type": "ncal:Alarm",
				"name": "Play alarm sound",
				"inputData": {},
				"hrefs": ["/play_alarm"]
			}
		],
		"events": []

	}
	)

@app.route('/td/speaker/play_welcome', methods=['GET', 'POST'])
def speaker_play_welcome_td():
	speaker.start_welcome()
	return make_response(jsonify({"Playing": "OK"}), 200)

@app.route('/td/speaker/play_alarm', methods=['GET', 'POST'])
def speaker_play_alarm_td():
	speaker.start_alarm()
	return make_response(jsonify({"Playing": "OK"}), 200)

@app.route('/td/speaker/play_ring', methods=['GET', 'POST'])
def speaker_play_ring_td():
	speaker.start_ring()
	return make_response(jsonify({"Playing": "OK"}), 200)

@app.errorhandler(404)
def not_found(error):
	return make_response(jsonify({'error': 'Not found'}), 404)

if __name__ == '__main__':
	app.run(host="0.0.0.0", debug=True)
