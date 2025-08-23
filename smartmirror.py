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
import io
from PIL import Image, ImageTk
import math

API_KEY = "f294f939822e1fc16e1d4cf9bc185be1"
CITY = "Rochester"
OVERRIDE_FILE = "/home/pi/smartmirror/poem_override.json"
current_override_msg = ""
override_active = False

# --- Resolve the public base safely (retry + short cache) ---
_BASE_URL = None
_BASE_TS = 0

def _resolve_base(max_wait=60):
	"""Try to resolve the live base URL with retries.
	Returns a string like 'https://xxxx.ngrok-free.app' (no trailing slash)."""
	import time
	last_err = None
	start = time.time()
	while time.time() - start < max_wait:
		try:
			base = get_ngrok_url().rstrip("/")
			if base.startswith("http"):
				return base
		except Exception as e:
			last_err = e
		time.sleep(2)
	# Give back whatever we had before (if any), otherwise raise
	if _BASE_URL:
		return _BASE_URL
	raise RuntimeError(f"Could not resolve ngrok/Render base (last error: {last_err})")

def base_url(stale_after=60):
	"""Return the current base URL, refreshing if cache is stale."""
	global _BASE_URL, _BASE_TS
	import time
	now = time.time()
	if not _BASE_URL or (now - _BASE_TS) > stale_after:
		try:
			_BASE_URL = _resolve_base(max_wait=30)
			_BASE_TS = now
		except Exception:
			# If we have an old one, keep using it; otherwise bubble up
			if not _BASE_URL:
				raise
	return _BASE_URL

def url(path):
	"""Join a path like '/reminders' to the current base."""
	return f"{base_url()}{path}"

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

# === Hearts config ===
HEART_FONT = ("URW Gothic L", 28)
HEART_COLOR = "red"
HEART_BG = "black"

# keep hearts outside the poem/flower by this many pixels
P_MARGIN = 20 # poem margin
F_MARGIN = 8 # flower margin

# remember last state so we can re-place hearts on layout changes without blinking
prev_heart_count = None
prev_layout_sig = None
heart_labels = [] # we keep/reuse these



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
		base = get_ngrok_url().rstrip("/")
		r = requests.get(url("/reminders"), timeout=6)
		r.raise_for_status()
		return r.json() # should be a list of strings
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
		response = requests.get(url("/override"))
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

# ============== HEARTS FUNCTIONS ================

def _layout_signature():
	"""Return (poem x,y,w,h, flower x,y,w,h) so we can detect layout changes."""
	try:
		px, py = label_poem.winfo_x(), label_poem.winfo_y()
		pw, ph = label_poem.winfo_width(), label_poem.winfo_height()
	except Exception:
		px = py = pw = ph = 0

	try:
		fx, fy = flower_canvas.winfo_x(), flower_canvas.winfo_y()
		fw = flower_canvas.winfo_width() or FLOWER_W
		fh = flower_canvas.winfo_height() or FLOWER_H
	except Exception:
		fx = fy = fw = fh = 0

	return (px, py, pw, ph, fx, fy, fw, fh)

def _rect_perimeter_points(x, y, w, h, n):
	"""
	Evenly distribute n points around the rectangle perimeter (clockwise),
	starting at top-left corner and marching along the edges.
	"""
	if n <= 0 or w <= 0 or h <= 0:
		return []

	# lengths of edges
	perim = 2 * (w + h)
	step = perim / n

	pts = []
	d = 0.0
	for _ in range(n):
		t = d % perim
		if t < w: # top edge: left -> right
			px, py = x + t, y
		elif t < w + h: # right edge: top -> bottom
			px, py = x + w, y + (t - w)
		elif t < w + h + w: # bottom edge: right -> left
			px, py = x + (w - (t - (w + h))), y + h
		else: # left edge: bottom -> top
			px, py = x, y + (h - (t - (w + h + w)))
		pts.append((int(px), int(py)))
		d += step
	return pts

def _points_around_rect(x, y, w, h, n):
	"""
	Return n (x,y) points marching clockwise around the rectangle boundary.
	Starts near the mid-top, spreads evenly.
	"""
	if n <= 0:
		return []
	per = 2*(w+h)
	step = per / n
	pts = []
	d = 0.0
	for _ in range(n):
		# walk distance d along the perimeter
		t = d % per
		if t < w: # top edge (left→right)
			px, py = x + t, y
		elif t < w + h: # right edge (top→bottom)
			px, py = x + w, y + (t - w)
		elif t < w + h + w: # bottom edge (right→left)
			px, py = x + (w - (t - (w + h))), y + h
		else: # left edge (bottom→top)
			px, py = x, y + (h - (t - (w + h + w)))
		pts.append((int(px), int(py)))
		d += step
	return pts

def _compute_dynamic_heart_positions(total):
	"""
	Build heart positions that hug the poem and the flower.
	Alternates: poem, flower, poem, flower...
	"""
	if total <= 0:
		return []

	# current geometry (and expand by margins so we don't overlap content)
	px, py, pw, ph, fx, fy, fw, fh = _layout_signature()

	# expand rectangles outward
	poem_rect = (px - P_MARGIN, py - P_MARGIN, pw + 2*P_MARGIN, ph + 2*P_MARGIN)
	flower_rect = (fx - F_MARGIN, fy - F_MARGIN, fw + 2*F_MARGIN, fh + 2*F_MARGIN)

	# split the amount roughly in half, but we’ll interleave
	n_poem = (total + 1) // 2
	n_flower = total // 2

	poem_pts = _rect_perimeter_points(*poem_rect, n_poem)
	flower_pts = _rect_perimeter_points(*flower_rect, n_flower)

	# interleave: p0, f0, p1, f1, ...
	out = []
	for i in range(max(len(poem_pts), len(flower_pts))):
		if i < len(poem_pts):
			out.append(poem_pts[i])
		if i < len(flower_pts):
			out.append(flower_pts[i])
	return out[:total]

def get_active_heart_rings():
	try:
		r = requests.get(url("/missyou/status"), timeout=5)
		r.raise_for_status()
		data = r.json()
		return int(data.get("active_rings", 0))
	except Exception as e:
		print("Error fetching heart data:", e)
		return 0

def update_hearts():
	"""Re-draw hearts when count OR layout changes. No blinking."""
	global heart_labels, prev_heart_count, prev_layout_sig

	# how many hearts to show
	try:
		count = get_active_heart_rings()
	except Exception:
		count = 0

	# has the poem or flower geometry changed?
	curr_sig = _layout_signature()

	must_refresh = (
		prev_heart_count is None or
		count != prev_heart_count or
		curr_sig != prev_layout_sig
	)

	if not must_refresh:
		root.after(1000, update_hearts)
		return

	# compute desired positions for current layout
	positions = _compute_dynamic_heart_positions(count)

	# add missing labels
	while len(heart_labels) < len(positions):
		lbl = tk.Label(root, text="❤", font=HEART_FONT, fg=HEART_COLOR, bg=HEART_BG)
		heart_labels.append(lbl)

	# remove extra labels
	while len(heart_labels) > len(positions):
		try:
			heart_labels[-1].destroy()
		except Exception:
			pass
		heart_labels.pop()

	# (re)place all labels (no destroy/create -> no blink)
	for lbl, (x, y) in zip(heart_labels, positions):
		lbl.place(x=x, y=y)

	# keep poem text and flower image above hearts if needed
	try:
		label_poem.lift()
		flower_canvas.lift()
	except Exception:
		pass

	prev_heart_count = count
	prev_layout_sig = curr_sig
	root.after(1000, update_hearts)

# === FLOWER (BOTTOM LEFT) =========================================
# Area where we draw the PNG (you can tweak size/position)
FLOWER_W, FLOWER_H = 380, 380 # drawing box size
FLOWER_X, FLOWER_Y = 100, -40 

flower_name_var = tk.StringVar(value="")
flower_canvas = tk.Canvas(root, width=FLOWER_W, height=FLOWER_H, highlightthickness=0, bg=BG)
flower_label = tk.Label(root, textvariable=flower_name_var, fg=COLOR, bg=BG, font=font_small, anchor="sw")

# place canvas & label (bottom-left)
flower_canvas.place(x=FLOWER_X, rely=1.0, y=FLOWER_Y, anchor="sw")
flower_label.place (x=PADDING, rely=1.0, y=FLOWER_Y - 20, anchor="nw")

# Keep references so the image isn't garbage-collected
_current_flower_photo = None
_current_flower_url = None

def _fetch_current_flower():
	"""GET {name, url} from the Pi via ngrok."""
	try:
		r = requests.get(url("/flower/current"), timeout=5)
		r.raise_for_status()
		# expected: {"name": "...", "file": "...", "url": "https://.../static/flowers/xxx.png"}
		return r.json()
	except Exception as e:
		print("flower: fetch error:", e)
		return None

def _load_photo_from_url(url, box_w, box_h):
	"""Load PNG from URL and scale into (box_w x box_h) preserving aspect."""
	try:
		resp = requests.get(url, timeout=8)
		resp.raise_for_status()
		img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
		iw, ih = img.size
		scale = min(box_w / iw, box_h / ih)
		nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
		img = img.resize((nw, nh), Image.LANCZOS)
		return ImageTk.PhotoImage(img)
	except Exception as e:
		print("flower: image load error:", e)
		return None

def update_flower():
	"""Refresh flower image/name if it changed (polls every 10 minutes)."""
	global _current_flower_photo, _current_flower_url

	data = _fetch_current_flower()
	if not data:
		flower_name_var.set("Flower unavailable")
		# try again in 5 minutes on error
		root.after(300000, update_flower)
		return

	# Update name immediately
	flower_name_var.set(data.get("name", ""))

	url = data.get("url")
	if url and url != _current_flower_url:
		photo = _load_photo_from_url(url, FLOWER_W, FLOWER_H)
		if photo:
			_current_flower_url = url
			_current_flower_photo = photo
			flower_canvas.delete("all")
			# center the image in the canvas
			cx, cy = FLOWER_W // 2, FLOWER_H // 2
			flower_canvas.create_image(cx, cy, image=_current_flower_photo, anchor="center")

	# poll again in 10 minutes (will pick up weekly rotation or manual next)
	root.after(600000, update_flower)

# ==================================================================

# === START ALL UPDATES ===
update_time()
update_weather()
rotate_poem()
check_override_loop()
update_reminders()
update_hearts()
update_flower()


root.mainloop()
