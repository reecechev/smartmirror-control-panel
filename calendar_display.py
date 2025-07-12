from datetime import datetime, timedelta
import os

# Apple Calendar Setup
import requests
import icalendar

# Google Calendar Setup
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow

# Google API scope
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# 1. Get events from Google Calendar
def get_google_events():
	creds = None
	if os.path.exists("token.json"):
		creds = Credentials.from_authorized_user_file("token.json", SCOPES)
	else:
		flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
		creds = flow.run_local_server(port=0)
		with open("token.json", "w") as token:
			token.write(creds.to_json())

	service = build('calendar', 'v3', credentials=creds)
	now = datetime.utcnow().isoformat() + 'Z'
	end = (datetime.utcnow() + timedelta(days=1)).isoformat() + 'Z'

	events_result = service.events().list(
	calendarId='primary', timeMin=now, timeMax=end,
	singleEvents=True, orderBy='startTime').execute()
	events = events_result.get('items', [])

	output = []
	for event in events:
		start = event['start'].get('dateTime', event['start'].get('date'))
		dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
		time_str = dt.strftime("%I:%M %p") if 'dateTime' in event['start'] else "All Day"
		summary = event.get('summary', 'No Title')
		output.append(f"{time_str} – {summary}")
	return output

# 2. Get events from Apple Calendar (.ics link)
def get_apple_events():
	try:
		url = "https://example.com/calendar.ics" # <-- Replace this later
		response = requests.get(url)
		cal = icalendar.Calendar.from_ical(response.text)

		today = datetime.now().date()
		output = []
		for component in cal.walk():
			if component.name == "VEVENT":
				start = component.get('dtstart').dt
				if hasattr(start, 'date') and start.date() == today:
					summary = component.get('summary')
					time_str = start.strftime("%I:%M %p")
					output.append(f"{time_str} – {summary}")
		return output
	except:
		return []

# 3. Combine both calendars
def get_combined_events():
	events = get_google_events() + get_apple_events()
	return sorted(events)

# 4. Test run
if __name__ == "__main__":
	print("📅 Today’s Events:")
	for event in get_combined_events():
		print("•", event)
