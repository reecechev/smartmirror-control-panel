import json
import os

REMINDERS_FILE = "/home/pi/smartmirror/webapp/reminders.json"

def reminders():
	if not os.path.exists(REMINDERS_FILE):
		return ["No reminders yet."]

	try:
		with open(REMINDERS_FILE, "r") as f:
			data = json.load(f)
		if not data:
			return ["No reminders yet."]
		return data[-3:] # show last 3 reminders
	except:
		return ["Error loading reminders."]
