import tkinter as tk
import requests
import time
from datetime import datetime, timedelta
import json
import random
from calendar_display import get_combined_events
from reminders import reminders
from app import get_override_message
from config import get_ngrok_url

API_KEY = "f294f939822e1fc16e1d4cf9bc185be1"
CITY = "Rochester"
OVERRIDE_FILE = "/home/pi/smartmirror/poem_override.json"
current_override_msg = ""
override_active = False
ngrokurl = get_ngrok_url()

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
		today_temps = [entry["main"]["temp"] for entry in data["list"] if datetime.fromtimestamp(entry["dt"]).date() == today]

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
			"humidity": humidity
		}
	else:
		return None

# === GUI SETUP ===
root = tk.Tk()
root.configure(bg="black")
root.attributes('-fullscreen', True)
root.config(cursor="none")

# === Fonts ===
font_time = ("URW Gothic L", 100)
font_temp = ("URW Gothic L", 70)
font_cond = ("URW Gothic L", 50)
font_small = ("URW Gothic L", 32)
font_medium = ("URW Gothic L", 38)
font_poem = ("URW Gothic L", 34)

PADDING = 40
COLOR = "white"
BG = "black"

# === TIME + WEATHER + LOCATION (TOP LEFT) ===
label_time = tk.Label(root, fg=COLOR, bg=BG, font=font_time)
label_city = tk.Label(root, fg=COLOR, bg=BG, font=font_small)
label_temp = tk.Label(root, fg=COLOR, bg=BG, font=font_temp)
label_condition = tk.Label(root, fg=COLOR, bg=BG, font=font_cond)
label_highLow = tk.Label(root, fg=COLOR, bg=BG, font=font_small)
label_wind = tk.Label(root, fg=COLOR, bg=BG, font=font_small)
label_humidity = tk.Label(root, fg=COLOR, bg=BG, font=font_small)

label_time.place(x=PADDING, y=30)
label_city.place(x=PADDING, y=150)
label_temp.place(x=PADDING, y=200)
label_condition.place(x=PADDING, y=290)
label_highLow.place(x=PADDING, y=370)
label_wind.place(x=PADDING, y=420)
label_humidity.place(x=PADDING, y=470)

def update_time():
	now = datetime.now().strftime("%I:%M %p").lstrip("0")
	label_time.config(text=now)
	root.after(1000, update_time)

def update_weather():
	weather = get_weather()
	if weather:
		label_city.config(text=CITY)
		label_temp.config(text=f"{weather['temp']}°F")
		label_condition.config(text=weather["condition"])
		label_highLow.config(text=f"High: {weather['high']}° Low: {weather['low']}°")
		label_wind.config(text=f"Wind: {weather['wind']} mph")
		label_humidity.config(text=f"Humidity: {weather['humidity']}%")
	else:
		label_city.config(text="Error retrieving data")
	root.after(120000, update_weather)

# === REMINDERS (TOP RIGHT) ===
reminders_text = tk.StringVar()
label_reminders_title = tk.Label(root, text="Reminders", fg=COLOR, bg=BG, font=font_medium, anchor="ne")
label_reminders = tk.Label(root, textvariable=reminders_text, fg=COLOR, bg=BG, font=font_small, justify="left", anchor="ne", wraplength=500)

label_reminders_title.place(relx=1.0, y=40, x=-PADDING, anchor="ne")
label_reminders.place(relx=1.0, y=100, x=-PADDING, anchor="ne")

def get_reminders():
	try:
		response = requests.get("https://smartmirror-app.onrender.com/reminders")
		response.raise_for_status()
		return response.json()
	except Exception as e:
		print("Error fetching reminders:", e)
		return ["Error loading reminders."]

def update_reminders():
	try:
		data = get_reminders()
		if not data:
			reminders_text.set("No reminders yet.")
		else:
			reminders_display = "\n".join(f"* {r}" for r in data[:5])
			reminders_text.set(reminders_display)
	except Exception:
		reminders_text.set("Error loading reminders.")
	root.after(60000, update_reminders)

# === POEM (BOTTOM RIGHT) ===
label_poem = tk.Label(
	root,
	fg=COLOR,
	bg=BG,
	font=font_poem,
	wraplength=500,
	justify="right",
	anchor="se"
)
label_poem.place(relx=1.0, rely=1.0, x=-PADDING, y=-PADDING, anchor="se")

poem_pool = []
shown_poems = []

def get_override_message():
	try:
		override_url = f"{ngrokurl}/override"
		response = requests.get(override_url)
		if response.status_code == 200:
			data = response.json()
			return data["override"]
		else:
			print("Failed to fetch override message: Status ", response.status_code)
	except Exception as e:
		print(f"Error fetching override message: {e}")
	return "" # fallback if error

def rotate_poem():
	global poem_pool, shown_poems

	if override_active:
		return

	try:
		with open("poems.json", "r", encoding="utf-8") as f:
			poem_data = json.load(f)
			all_poems = [f'{p.get("text", "").strip()}\n- {p.get("author", "Unknown").strip()}' for p in poem_data.get("display", []) if p.get("text")]
	except:
		all_poems = []

	# === GET ACTIVE REMINDERS ===
	try:
		with open("/home/pi/smartmirror/webapp/reminders.json", "r") as f:
			reminder_data = json.load(f)
			num_reminders = len(reminder_data)
	except:
		num_reminders = 0

	# === ESTIMATE SPACE USED ===
	LINE_HEIGHT = 40 # in pixels
	DISPLAY_HEIGHT = 1080
	RESERVED_PADDING = 100 # top/bottom + buffer
	reminder_height = num_reminders * LINE_HEIGHT

	available_height = DISPLAY_HEIGHT - RESERVED_PADDING - reminder_height
	max_poem_lines = available_height // LINE_HEIGHT
	
	# === FILTER POEMS BASED ON AVAILABLE SPACE ===
	filtered_poems = [p for p in all_poems if len(p.splitlines()) <= max_poem_lines]

	# Update poem rotation pool
	shown_poems = [p for p in shown_poems if p in filtered_poems]
	poem_pool = [p for p in filtered_poems if p not in shown_poems]
	random.shuffle(poem_pool)

	if not poem_pool and filtered_poems:
		poem_pool = filtered_poems.copy()
		random.shuffle(poem_pool)
		shown_poems.clear()
	
	if poem_pool:
		next_poem = poem_pool.pop(0)
		shown_poems.append(next_poem)
		fade_out_poem(next_poem)

	else:
		label_poem.config(text="No poems found or all too long")
	root.after(300000, rotate_poem)

def fade_out_poem(new_poem, step=0):
	if step > 10:
		label_poem.config(text=new_poem)
		fade_in_poem(new_poem)
		return

	fade = hex(int(255 * (1 - step / 10)))[2:].zfill(2)
	color = f"#{fade}{fade}{fade}"
	label_poem.config(fg=color)
	root.after(30, lambda: fade_out_poem(new_poem, step + 1))

def fade_in_poem(new_poem, step=0):
	try:
		text, author = new_poem.split("\n", 1)
	except ValueError:
		text, author = new_poem, "Unknown"

	fade = hex(int(255 * (step / 10)))[2:].zfill(2)
	color = f"#{fade}{fade}{fade}"

	if step > 10:
		return
	if step == 0:
		with open("current_poem.json", "w", encoding="utf-8") as f:
			json.dump({"text": text.strip(), "author": author.strip()}, f)

	if override_active:
		label_poem.config(
			text=new_poem,
			fg=color,
			font=("URW Chancery L", 40, "italic"),
			justify="center",
			anchor="center"
		)
	else:
		label_poem.config(
			text=new_poem,
			fg=color,
			font=font_poem, # ← your normal poem font
			justify="right",
			anchor="ne"
		)

	root.after(30, lambda: fade_in_poem(new_poem, step + 1))

def check_override_loop():
	global current_override_msg, override_active
	override_msg = get_override_message()

	print("override froms erver: ", override_msg)
	print("current message on screen: ", current_override_msg)

	if override_msg is not None and override_msg.strip() != "" and override_msg != current_override_msg:
		current_override_msg = override_msg
		override_active = True
		label_poem.config(
			text=current_override_msg,
			fg=COLOR,
			font=("URW Chancery L", 40, "italic"),
			justify="center",
			anchor="center"
		)
		fade_in_poem(current_override_msg)
	elif not override_msg and override_active:
		override_active = False
		current_override_msg = ""
		rotate_poem()

	root.after(15000, check_override_loop) # Check every 15 seconds

def get_active_heart_rings():
	try:
		response = requests.get("http://localhost:5000/missyou/rings")
		if response.status_code == 200:
			timestamps = response.json()
			now = datetime.utcnow()
			active_rings = 0
			for i, ts in enumerate(timestamps):
				ring_time = datetime.fromisoformat(ts)
				elapsed = now - ring_time
				if elapsed < timedelta(minutes=30):
					active_rings += 1
			return active_rings
		else:
			return 0
	except Exception as e:
		print("Error fetching heart data:", e)
		return 0

def update_hearts():
	try:
		active_hearts = get_active_heart_rings()
		for i in range(active_hearts):
			heart = tk.Label(root, text="❤️", font=("URW Gothic L", 24 + i * 4), fg="red", bg="black")
			heart.place(x=100, y=700 - i * 40) # Adjust position if needed
	except Exception as e:
		print("Error updating hearts:", e)

# === CALENDAR (BOTTOM LEFT) ===
calendar_text = tk.StringVar()
label_calendar_title = tk.Label(root, text="Calendar", fg=COLOR, bg=BG, font=font_medium, anchor="sw")
label_calendar = tk.Label(root, textvariable=calendar_text, fg=COLOR, bg=BG, font=font_small, justify="left", anchor="sw", wraplength=500)

label_calendar_title.place(x=PADDING, rely=1.0, y=-140, anchor="sw")
label_calendar.place(x=PADDING, rely=1.0, y=-100, anchor="sw")

def update_calendar():
	try:
		events = get_combined_events()
		if not events:
			calendar_display = "No events today"
		else:
			calendar_display = "\n".join(f"• {event}" for event in events)
			calendar_text.set(calendar_display)
	except Exception as e:
		calendar_text.set("Calendar error")

	root.after(180000, update_calendar)

# === START ALL UPDATES ===
update_time()
update_weather()
rotate_poem()
check_override_loop()
update_reminders()
update_calendar()
update_hearts()

root.mainloop()
