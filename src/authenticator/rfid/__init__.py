# -*- coding: utf8 -*-

import RPi.GPIO as GPIO
from .MFRC522 import *
import signal
import datetime
import threading
import time
import pygame

continue_reading = True
authenticated = False

def log(log_entry):
	timestamp = datetime.datetime.now().strftime("%I:%M:%S")
	print("[{}] {}".format(timestamp, log_entry))


valid_users = [102]


class RFIDReader:
	def __init__(self):
		# Hook the SIGINT for cleaning up.
		#signal.signal(signal.SIGINT, self.__exit__())

		# Variable indicating authentication status.
		self.authenticated = False

		# Create new reader instance.
		self.MIFAREReader = MFRC522()

		print("Created MFRC522 instance.")

	def __exit__(self, exc_type, exc_val, exc_tb):
		# Clean up GPIO resource access.
		global continue_reading
		continue_reading = False
		GPIO.cleanup()
		log("Cleanup finished.")

	def start(self):
		global continue_reading
		continue_reading = True
		loop = threading.Thread(target=self.read_loop, args=())
		loop.daemon = True
		loop.start()
		print("!!!!")

	def stop(self):
		global continue_reading
		continue_reading = False

	def read_loop(self):
		# This loop keeps checking for chips. If one is near it will get the UID and authenticate
		while continue_reading:

			# Scan for cards
			(status, TagType) = self.MIFAREReader.MFRC522_Request(self.MIFAREReader.PICC_REQIDL)

			# Card is detected.
			if status == self.MIFAREReader.MI_OK:
				log("Card detected")

			# Get the UID of the card.
			(status, uid) = self.MIFAREReader.MFRC522_Anticoll()

			#log("UID:" + str(uid[0]))

			# Check if status is ok and user is valid.
			if status == self.MIFAREReader.MI_OK:
				if uid[0] in valid_users:
					global authenticated
					if authenticated == False:
						self.set_authenticated()
					log("uid= " + str(uid[0]) + "Valid user authenticated successfully.")
				else:
					log("uid= " + str(uid[0]) + "User is not valid!")
			#else:
				#log("Error when authenticating")

			GPIO.cleanup()

	def set_authenticated(self):
		# Set authenticated status for 5 seconds.
		global authenticated
		authenticated = True
		log("Authenticated is " + str(authenticated))
		pygame.mixer.init()
		pygame.mixer.music.load("ring.mp3")
		pygame.mixer.music.play()
		time.sleep(4)
		pygame.mixer.music.stop()

		def close_authentication():
			time.sleep(30)
			self.authenticated = False
			global authenticated
			authenticated = False
			log("Close authenticated status window.")

		wait_and_close = threading.Thread(target=close_authentication, args=())
		wait_and_close.daemon = True
		wait_and_close.start()

		#log("Authenticated: " + str(self.authenticated))
	
	def is_authenticated(self):
		global authenticated
		log("authenticated again" + str(authenticated))
		return authenticated
