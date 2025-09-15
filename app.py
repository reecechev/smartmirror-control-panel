from flask import Flask, request, jsonify, render_template
from flask import Flask, render_template, request, redirect, make_response, Response
import os, json
from flask_cors import CORS
from datetime import datetime, timedelta
from config import get_ngrok_url
from zoneinfo import ZoneInfo
from flask import send_from_directory
from pathlib import Path
from werkzeug.utils import secure_filename
from urllib.parse import urlparse
from lights import get_lights
import requests

L = get_lights()

app = Flask(__name__)
CORS(app)


REMINDERS_FILE = "reminders.json"
POEMS_FILE = "poems.json"
OVERRIDE_FILE = "poem_override.json"
NGROK_FILE = os.path.join(os.path.dirname(__file__), "ngrok.json")
FAVORITES_FILE = "favorites.json"
REMOVED_FILE = "removed.json"
STATIC_BASE = "https://ostrich-pretty-lab.ngrok.app".rstrip("/")
MISSYOU_FILE = "missyou.json"

# If L has real pixels, we’re on the Pi. Otherwise we’re on Render.
RUN_LOCAL = hasattr(L, "pixels")

def _forward_to_pi(path: str, payload: dict | None = None):
	"""Send the same request to the Pi (ngrok base) when running on Render."""
	url = f"{STATIC_BASE}{path}"
	try:
		resp = requests.post(url, json=(payload or {}), timeout=5)
		try:
			body = resp.json()
		except Exception:
			body = {"status": "error", "message": "Pi returned non-JSON"}
		return body, resp.status_code
	except Exception as e:
		return {"status": "error", "message": f"forward fail: {e}"}, 502

@app.route("/")
def home():
	# Prefer static base if defined
	base = STATIC_BASE

	# Fallback to ngrok.json only if no static base configured
	if not base:
		try:
			with open(NGROK_FILE, "r", encoding="utf-8") as f:
				data = json.load(f) or {}
				base = (data.get("base", "") or "").strip().rstrip("/")
		except Exception:
			base = ""

	if base:
	# If we hit Render (or any non-ngrok host), redirect to the static base
		try:
			from urllib.parse import urlparse
			base_host = urlparse(base).netloc
			cur_host = request.headers.get("Host", "")
			if cur_host and cur_host != base_host:
				return redirect(base, code=302)
		except Exception:
			# If anything looks odd, just render the UI instead of bouncing
			pass

		# We're already on the right host -> render the app normally
		return render_template("index.html") # or your real main page

	# No base at all -> show tiny "waiting" page (very rare)
	html = "<h3>Waiting for ngrok...</h3><p>POST a JSON {\"base\":\"https://...\"} to /ngrok</p>"
	headers = {
		"Cache-Control": "no-store, max-age=0",
		"CDN-Cache-Control": "no-store",
		"Pragma": "no-cache",
		"Expires": "0",
	}
	return Response(html, status=503, headers=headers)

def _append_json(path, obj):
	try:
		with open(path, "r", encoding="utf-8") as f:
			arr = json.load(f)
			if not isinstance(arr, list):
				arr = []
	except FileNotFoundError:
		arr = []
	except Exception:
		arr = []
	arr.append(obj)
	with open(path, "w", encoding="utf-8") as f:
		json.dump(arr, f, ensure_ascii=False, indent=2)

# ---- Flowers config ----
FLOWER_FOLDER = os.path.join(os.path.dirname(__file__), "static", "flowers")
os.makedirs(FLOWER_FOLDER, exist_ok=True)

FLOWER_STATE_PATH = os.path.join(os.path.dirname(__file__), "flowers_state.json")
TZ_NY = ZoneInfo("America/New_York")

ALLOWED_EXTS = {".png", ".jpg", ".jpeg"}

def _list_flowers_from_disk():
	"""Return [{'name','file'}] for images in static/flowers."""
	items = []
	for p in sorted(Path(FLOWER_FOLDER).glob("*.*")):
		if p.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
			continue
		nice = p.stem.replace("_", " ").title()
		items.append({"name": nice, "file": p.name})
	return items

def _load_flower_state():
	try:
		with open(FLOWER_STATE_PATH, "r", encoding="utf-8") as f:
			return json.load(f)
	except Exception:
		return {"index": 0, "changed_at": datetime.now(TZ_NY).isoformat()}

def _save_flower_state(state):
	with open(FLOWER_STATE_PATH, "w", encoding="utf-8") as f:
		json.dump(state, f, indent=2)

def _next_wed_9am(after_dt):
	dt = after_dt.astimezone(TZ_NY)
	while dt.weekday() != 2: # Wednesday = 2
		dt += timedelta(days=1)
	due = dt.replace(hour=9, minute=0, second=0, microsecond=0)
	if due <= after_dt.astimezone(TZ_NY):
		due += timedelta(days=7)
	return due

def _maybe_rotate_weekly(state, now_et):
	"""If it’s past the next Wed 9am since last change, bump index and persist."""
	try:
		changed_at = datetime.fromisoformat(state.get("changed_at")).astimezone(TZ_NY)
	except Exception:
		changed_at = now_et

	due = _next_wed_9am(changed_at)
	if now_et >= due:
		state["index"] = int(state.get("index", 0)) + 1 # no modulo here
		state["changed_at"] = now_et.isoformat()
		_save_flower_state(state)

	return state

def load_reminders():
	try:
		with open(REMINDERS_FILE, "r") as f:
			return json.load(f)
	except FileNotFoundError:
		return []

def save_reminders(reminders):
	with open(REMINDERS_FILE, "w") as f:
		json.dump(reminders, f)

@app.route("/flowers", methods=["GET"])
def flowers_page():
	return render_template("flowers.html")

@app.route("/flower/current", methods=["GET"])
def flower_current():
	base = get_ngrok_url().rstrip("/")
	now_et = datetime.now(TZ_NY)

	flowers = _list_flowers_from_disk()
	if not flowers:
		return jsonify({"error": "No flower images found"}), 503

	state = _load_flower_state()
	state = _maybe_rotate_weekly(state, now_et)

	idx = int(state.get("index", 0)) % len(flowers)
	flower = flowers[idx]
	flower_url = f"{base}/static/flowers/{flower['file']}"
	return jsonify({"name": flower["name"], "file": flower["file"], "url": flower_url})


@app.route("/flower/list", methods=["GET"])
def flower_list():
	return jsonify(_list_flowers_from_disk())


@app.route("/flower/next", methods=["POST"])
def flower_next():
	flowers = _list_flowers_from_disk()
	if not flowers:
		return jsonify({"error": "No flower images found"}), 503

	state = _load_flower_state()
	state["index"] = (int(state.get("index", 0)) + 1) % len(flowers)
	state["changed_at"] = datetime.now(TZ_NY).isoformat()
	_save_flower_state(state)
	return jsonify(state)

@app.route("/static/flowers/<path:filename>")
def flowers_static(filename):
	return send_from_directory(FLOWER_FOLDER, filename)

@app.route("/flower/upload", methods=["POST"])
def flower_upload():
	"""
	Accept a file from a <form> field named 'file', save to static/flowers,
	and return simple status JSON. Newly uploaded images are auto-included
	because the rotation reads from disk.
	"""
	if "file" not in request.files:
		return jsonify({"error": "No file part"}), 400

	f = request.files["file"]
	if f.filename == "":
		return jsonify({"error": "No selected file"}), 400

	name = secure_filename(f.filename)
	ext = os.path.splitext(name)[1].lower()
	if ext not in ALLOWED_EXTS:
		return jsonify({"error": "Only .png/.jpg allowed"}), 400

	save_path = os.path.join(FLOWER_FOLDER, name)
	f.save(save_path)

	return jsonify({"status": "ok", "saved": name})


# ======= POEMS ===========
@app.route("/poems", methods=["GET"])
def poems():
	poems = load_poems()
	override = get_override_message()

	try:
		with open("current_poem.json", "r", encoding="utf-8") as f:
			current_poem = json.load(f)
	except FileNotFoundError:
		current_poem = None

	return render_template("poems.html", poems=poems, override=override)

@app.route('/override')
def get_override():
	with open('poem_override.json', 'r') as f:
		data = json.load(f)
	return jsonify(data)

@app.route('/clear_override', methods=["POST"])
def clear_override():
	try:
		with open(OVERRIDE_FILE, "w") as f:
			json.dump({"override": ""}, f)

		# Turn lights off both locally or via Render
		if RUN_LOCAL and hasattr(L, "off"):
			L.off()
			return redirect("/poems")
		else:
			_forward_to_pi("/lights/off", {})
			return redirect("/poems")
	except Exception as e:
		return jsonify({"status": "error", "message": str(e)})

@app.route("/add_poem", methods=["POST"])
def add_poem():
	# Accept JSON or classic form POST
	payload = request.get_json(silent=True) or request.form

	# Field name compatibility
	text = (payload.get("text") or payload.get("poem_text") or "").strip()
	author = (payload.get("author") or "Unknown").strip()

	# display defaults to True; honor legacy checkbox "is_favorite"
	display = payload.get("display")
	if isinstance(display, str):
		display = display.lower() not in ("false", "0", "no", "off")
	if display is None:
		display = bool(payload.get("is_favorite", True))

	if not text:
		if request.is_json:
			return jsonify({"error": "Poem text is required."}), 400
		return redirect("/poems")

	poems = load_poems()
	poems.append({"text": text, "author": author, "display": display})
	save_poems(poems)

	if request.is_json:
		return jsonify({"status": "ok", "count": len(poems)}), 201
	return redirect("/poems")

# Optional: JSON-friendly alias you can call from curl or the app
@app.route("/poems/add", methods=["POST"])
def poems_add():
	return add_poem()

def load_poems():
	try:
		with open(POEMS_FILE, "r", encoding="utf-8") as f:
			data = json.load(f)
			return data if isinstance(data, list) else []
	except FileNotFoundError:
		return []
	except Exception as e:
		print("load_poems error:", e)
		return []

def save_poems(poems):
	# atomic write to avoid corrupting the file on crash
	tmp = POEMS_FILE + ".tmp"
	with open(tmp, "w", encoding="utf-8") as f:
		json.dump(poems, f, ensure_ascii=False, indent=2)
	os.replace(tmp, POEMS_FILE)

def set_override_message(msg):
	with open(OVERRIDE_FILE, "w") as f:
		json.dump({"override": msg}, f)

def get_override_message():
	try:
		with open(OVERRIDE_FILE, "r") as f:
			return json.load(f).get("override", "")
	except:
		return ""

@app.route("/favorite_poem", methods=["POST"])
def favorite_poem():
	try:
		# read the poem currently on screen
		with open("current_poem.json", "r", encoding="utf-8") as f:
			current_poem = json.load(f)

		# stash in favorites.json (list)
		_append_json(FAVORITES_FILE, current_poem)

		# back to the poems page (or return JSON if you prefer)
		return redirect("/poems")
	except Exception as e:
		return f"Error favoriting poem: {e}", 500


@app.route("/remove_poem", methods=["POST"])
def remove_poem():
	try:
		# poem currently showing
		with open("current_poem.json", "r", encoding="utf-8") as f:
			current_poem = json.load(f)

		# load poems list
		with open("poems.json", "r", encoding="utf-8") as f:
			poems = json.load(f)
			if not isinstance(poems, list):
				poems = []

		# locate a matching poem and set display=False
		ct = current_poem.get("text", "").strip()
		ca = current_poem.get("author", "").strip()

		changed = False
		for p in poems:
			if p.get("text", "").strip() == ct and p.get("author", "").strip() == ca:
				p["display"] = False
				changed = True
				break

		if changed:
			with open("poems.json", "w", encoding="utf-8") as f:
				json.dump(poems, f, ensure_ascii=False, indent=2)

		# also log it in removed.json (optional, useful history)
		_append_json(REMOVED_FILE, current_poem)

		return redirect("/poems")
	except Exception as e:
		return f"Error removing poem: {e}", 500


@app.route("/current_poem")
def current_poem():
    try:
        with open("current_poem.json", "r", encoding="utf-8") as f:
            poem_data = json.load(f)
            text = poem_data.get("text", "").strip()
            author = poem_data.get("author", "Unknown")
            response = jsonify({"text": text, "author": author})
            
            return response
    except Exception as e:
        error_response = jsonify({"error": f"Error loading poem: {e}"})
        print("Current directory:", os.getcwd())
        
        return error_response


# ============ MISS YOU ===============
@app.route("/missyou")
def missyou():
	return render_template("missyou.html")

def _ensure_parent_dir(path):
	# (keeps things safe even if you later move the file)
	Path(path).parent.mkdir(parents=True, exist_ok=True)

def load_missyou_data():
	"""Always return a dict with keys: clicks (int), rings (list of ISO UTC strings)."""
	try:
		with open(MISSYOU_FILE, "r", encoding="utf-8") as f:
			data = json.load(f)
			if not isinstance(data, dict):
				raise ValueError("bad shape")
			data.setdefault("clicks", 0)
			data.setdefault("rings", [])
			return data
	except Exception:
		# File missing or corrupt -> start fresh
		return {"clicks": 0, "rings": []}

def save_missyou_data(data):
	"""Persist safely."""
	_ensure_parent_dir(MISSYOU_FILE)
	with open(MISSYOU_FILE, "w", encoding="utf-8") as f:
		json.dump(data, f, ensure_ascii=False, indent=2)

@app.route("/missyou/tap", methods=["POST"])
def tap_heart():
	data = load_missyou_data()

	# Bump clicks
	data["clicks"] = int(data.get("clicks", 0)) + 1

	# Every 10 clicks -> add a ring timestamp (UTC, no microseconds)
	if data["clicks"] % 10 == 0:
		now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
		data["rings"].append(now)
		# keep list bounded so file never grows unbounded
		if len(data["rings"]) > 200:
			data["rings"] = data["rings"][-200:]

	save_missyou_data(data)

	# pulse red quickly
	try:
		payload = {"color": (255, 0, 0), "ms": 180}

		if RUN_LOCAL and hasattr(L, "pulse"):
			L.pulse(color=payload["color"], ms=payload["ms"])
		else:
			_forward_to_pi("/lights/pulse", payload)
	except Exception as e:
		print("lights/pulse error:", e)

	return jsonify({"clicks": data["clicks"], "rings": len(data["rings"])})

@app.route("/missyou/status")
def missyou_status():
	"""Return how many rings are still 'active' (<= 30 minutes old)."""
	try:
		data = load_missyou_data()
		now = datetime.utcnow()
		active = 0
		for ts in data.get("rings", []):
			try:
				# accept both "...Z" and "...Z.sss"
				ts_clean = ts.replace("Z", "")
				if "." in ts_clean:
					ts_clean = ts_clean.split(".", 1)[0]
				ring_time = datetime.fromisoformat(ts_clean)
				if (now - ring_time).total_seconds() <= 30 * 60:
					active += 1
			except Exception:
				continue
		return jsonify({"active_rings": active})
	except Exception as e:
		return jsonify({"error": str(e)}), 500

@app.route("/missyou/rings", methods=["GET"])
def get_ring_timestamps():
	data = load_missyou_data()
	return jsonify(data.get("rings", []))

@app.route("/poem_override", methods=["POST"])
def poem_override():
	_msg = request.form.get("override_msg", "")
	set_override_message(_msg)

	try:
		# fade purple -> blue (2s)
		if RUN_LOCAL and hasattr(L, "fade_between"):
			L.fade_between((128, 0, 128), (0, 0, 255), 2.0)
		else:
			_forward_to_pi("/lights/fade",
				{"c1": [128, 0, 128], "c2": [0, 0, 255], "seconds": 2.0})

		# then blue -> red (2s)
		if RUN_LOCAL and hasattr(L, "fade_between"):
			L.fade_between((0, 0, 255), (255, 0, 0), 2.0)
		else:
			_forward_to_pi("/lights/fade",
				{"c1": [0, 0, 255], "c2": [255, 0, 0], "seconds": 2.0})

	except Exception as e:
		print("lights/fade error:", e)

	return redirect("/poems")

@app.route("/calendar")
def calendar():
	return render_template("calendar.html")


# =========== REMINDERS =============
@app.route("/reminders_page")
def reminders_page():
	return render_template("reminders.html")

@app.route("/add_reminder", methods=["POST"])
def add_reminder():
	data = request.json
	new_reminder = data.get("reminder")

	if not new_reminder:
		return jsonify({"error": "No reminder provided"}), 400

	reminders = load_reminders()
	reminders.append(new_reminder)
	save_reminders(reminders)

	return jsonify({"status": "success", "reminders": reminders})

@app.route("/reminders", methods=["GET"])
def get_reminders():
	return jsonify(load_reminders())

@app.route("/edit_reminder", methods=["POST"])
def edit_reminder():
	data = request.json
	index = data.get("index")
	new_text = data.get("new_text")

	reminders = load_reminders()
	try:
		reminders[index] = new_text
		save_reminders(reminders)
		return jsonify({"status": "success", "reminders": reminders})
	except IndexError:
		return jsonify({"error": "Reminder not found"}), 404

@app.route("/delete_reminder", methods=["POST"])
def delete_reminder():
	data = request.json
	index = data.get("index")

	reminders = load_reminders()
	try:
		removed = reminders.pop(index)
		save_reminders(reminders)
		return jsonify({"status": "deleted", "removed": removed, "reminders": reminders})
	except IndexError:
		return jsonify({"error": "Reminder not found"}), 404

# ======================================================================================================    LIGHTS    =====================================================================================================================

@app.route("/lights/off", methods=["POST", "GET"])
def lights_off():
	try:
		if RUN_LOCAL:
			L.off()
			return jsonify({"status": "ok", "mode": "off"})
		else:
			body, code = _forward_to_pi("/lights/off")
			return jsonify(body), code
	except Exception as e:
		return jsonify({"error": str(e)}), 500


@app.route("/lights/set", methods=["POST"])
def lights_set():
	"""
	JSON body supports either:
	{"r":255,"g":0,"b":180,"w":0,"brightness":0.3}
	or
	{"hex":"#FF00B4","w":0,"brightness":0.3}
	"""
	try:
		data = request.get_json(force=True) or {}
		# On Render, forward exact payload to the Pi
		if not RUN_LOCAL:
			body, code = _forward_to_pi("/lights/set", data)
			return jsonify(body), code

		# Local behavior (Pi)
		if "brightness" in data and hasattr(L, "pixels"):
			try:
				L.pixels.brightness = float(data.get("brightness"))
			except Exception:
				pass

		if "hex" in data:
			hx = data["hex"].lstrip("#")
			r = int(hx[0:2], 16); g = int(hx[2:4], 16); b = int(hx[4:6], 16)
			w = int(data.get("w", 0))
		else:
			r = int(data.get("r", 0)); g = int(data.get("g", 0)); b = int(data.get("b", 0))
			w = int(data.get("w", 0))

		L.set_color(r, g, b, w)
		return jsonify({"status": "ok", "color": {"r": r, "g": g, "b": b, "w": w}})
	except Exception as e:
		return jsonify({"error": str(e)}), 400


@app.route("/lights/mode", methods=["POST"])
def lights_mode():
	"""
	JSON body:
	{"mode":"pulse|wave|rainbow|fade","args":{...}}
	Examples:
	{"mode":"pulse","args":{"color":[0,0,255,0],"seconds":2.0}}
	{"mode":"wave","args":{"base":[0,120,255,0],"wavelength":18,"speed":0.02}}
	{"mode":"rainbow","args":{"speed":0.02}}
	{"mode":"fade","args":{"c1":[255,0,0,0],"c2":[0,0,255,0],"period":3.0}}
	"""
	try:
		data = request.get_json(force=True) or {}
		if not RUN_LOCAL:
			body, code = _forward_to_pi("/lights/mode", data)
			return jsonify(body), code

		mode = (data.get("mode") or "").lower()
		args = data.get("args") or {}

		if mode == "pulse" and hasattr(L, "pulse"):
			L.pulse(tuple(args.get("color", [0, 0, 255, 0])), float(args.get("seconds", 2.0)))
		elif mode == "wave" and hasattr(L, "wave"):
			L.wave(tuple(args.get("base", [0, 120, 255, 0])),
				int(args.get("wavelength", 18)),
				float(args.get("speed", 0.02)))
		elif mode == "rainbow" and hasattr(L, "rainbow"):
			L.rainbow(float(args.get("speed", 0.02)), int(args.get("step", 2)))
		elif mode == "fade" and hasattr(L, "fade_between"):
			L.fade_between(tuple(args.get("c1", [255, 0, 0, 0])),
					tuple(args.get("c2", [0, 0, 255, 0])),
					float(args.get("period", 3.0)))
		else:
			return jsonify({"error": f"unknown mode or not supported: {mode}"}), 400

		return jsonify({"status": "ok", "mode": mode})
	except Exception as e:
		return jsonify({"error": str(e)}), 400


# Convenience explicit endpoints (your app already calls those)
@app.route("/lights/pulse", methods=["POST"])
def lights_pulse():
	try:
		data = request.get_json(silent=True) or {}
		if not RUN_LOCAL:
			body, code = _forward_to_pi("/lights/pulse", data)
			return jsonify(body), code

		color = tuple(data.get("color", [255, 0, 0, 0]))
		ms = int(data.get("ms", 180))
		L.pulse(color, ms=ms)
		return jsonify({"status": "ok"})
	except Exception as e:
		return jsonify({"error": str(e)}), 400


@app.route("/lights/fade", methods=["POST"])
def lights_fade():
	try:
		data = request.get_json(silent=True) or {}
		if not RUN_LOCAL:
			body, code = _forward_to_pi("/lights/fade", data)
			return jsonify(body), code

		c1 = tuple(data.get("c1", [255, 0, 0, 0]))
		c2 = tuple(data.get("c2", [0, 0, 255, 0]))
		period = float(data.get("seconds", 3.0))
		# legacy arg kept for compatibility; fade_between loops by design
		loop = bool(data.get("loop", False))
		L.fade_between(c1, c2, period)
		return jsonify({"status": "ok"})
	except Exception as e:
		return jsonify({"error": str(e)}), 400


@app.route("/lights/weather", methods=["POST"])
def lights_weather():
	try:
		data = request.get_json(force=True) or {}
		if not RUN_LOCAL:
			body, code = _forward_to_pi("/lights/weather", data)
			return jsonify(body), code

		cond = (data.get("condition", "") or "").lower()
		if hasattr(L, "weather"):
			L.weather(cond)
			return jsonify({"status": "ok", "condition": cond})
		return jsonify({"error": "weather() not implemented"}), 400
	except Exception as e:
		return jsonify({"error": str(e)}), 400


@app.route("/lights/override", methods=["POST"])
def lights_override():
	try:
		data = request.get_json(silent=True) or {}
		if not RUN_LOCAL:
			body, code = _forward_to_pi("/lights/override", data)
			return jsonify(body), code

		secs = float(data.get("seconds", 2.0))
		if hasattr(L, "override_burn"):
			L.override_burn(seconds=secs)
			return jsonify({"status": "ok"})
		return jsonify({"error": "override_burn() not implemented"}), 400
	except Exception as e:
		return jsonify({"error": str(e)}), 500


@app.route("/lights/heart", methods=["POST"])
def lights_heart():
	try:
		if RUN_LOCAL and hasattr(L, "heart_pulse"):
			L.heart_pulse()
			return jsonify({"status": "ok"}), 200
		else:
			body, code = _forward_to_pi("/lights/heart", {})
			return jsonify(body), code
	except Exception as e:
		return jsonify({"status": "error", "message": str(e)}), 500

# ===================================================================================================    NGROK    =========================================================================================================================

def _read_ngrok_file():
	try:
		with open(NGROK_FILE, "r", encoding="utf-8") as f:
			return json.load(f)
	except Exception:
		return {}

@app.route("/ngrok", methods=["GET", "POST"])
def ngrok_route():
	# If you have a static domain, don't allow changes to it by POST
	if request.method == "POST":
		if STATIC_BASE:
			return jsonify({"status": "ignored", "reason": "static base configured"}), 200

		data = request.get_json(silent=True) or {}
		base = (data.get("base") or "").strip().rstrip("/")
		if not (base.startswith("http://") or base.startswith("https://")):
			return jsonify({"error": "invalid base"}), 400

		with open(NGROK_FILE, "w", encoding="utf-8") as f:
			json.dump({"base": base, "updated_at": datetime.utcnow().isoformat() + "Z"}, f)
		return jsonify({"status": "ok"})

	# GET: report current base (prefer static)
	payload = {"base": STATIC_BASE} if STATIC_BASE else {}
	if not payload.get("base"):
		try:
			with open(NGROK_FILE, "r", encoding="utf-8") as f:
				payload = json.load(f)
		except Exception:
			payload = {}

	headers = {
		"Cache-Control": "no-store, max-age=0",
		"CDN-Cache-Control": "no-store",
		"Pragma": "no-cache",
		"Expires": "0",
	}
	return make_response(jsonify(payload), 200, headers)


if __name__ == "__main__":
	app.run(host="0.0.0.0", port=5000)
