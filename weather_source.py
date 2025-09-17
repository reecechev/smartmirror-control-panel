from datetime import datetime
import os
import requests

# Copy these from smartmirror.py (or read from env if you prefer)
API_KEY = "f294f939822e1fc16e1d4cf9bc185be1"
CITY = "Rochester"

def get_weather():
	url = f"http://api.openweathermap.org/data/2.5/forecast?q={CITY}&units=imperial&appid={API_KEY}"
	response = requests.get(url)
	if response.status_code == 200:
		data = response.json()
		temp = round(data["list"][0]["main"]["temp"])
		condition = data["list"][0]["weather"][0]["description"].capitalize()
		wind = round(data["list"][0]["wind"]["speed"])
		humidity = data["list"][0]["main"]["humidity"]

		today = datetime.now().date()
		today_temps = [
			entry["main"]["temp"] for entry in data["list"]
			if datetime.fromtimestamp(entry["dt"]).date() == today
		]
		if today_temps:
			high = round(max(today_temps))
			low = round(min(today_temps))
		else:
			high = low = temp

		return {
			"temp": temp,
			"high": high,
			"low": low,
			"condition": condition,
			"wind": wind,
			"humidity": humidity,
		}
	return None
