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

app = Flask(__name__)
CORS(app)


REMINDERS_FILE = "reminders.json"
POEMS_FILE = "poems.json"
OVERRIDE_FILE = "poem_override.json"
NGROK_FILE = os.path.join(os.path.dirname(__file__), "ngrok.json")


@app.route("/")
def home():
	# read base from file (robust against empty/corrupt file)
	try:
		with open(NGROK_FILE, "r", encoding="utf-8") as f:
			data = json.load(f) or {}
			base = (data.get("base", "") or "").strip().rstrip("/")
	except Exception:
		base = ""

	if base:
		base_host = urlparse(base).netloc
		cur_host = request.headers.get("Host", "")

		# if we're not on the ngrok host yet, bounce there
		if base_host and cur_host and (cur_host != base_host):
			return redirect(base, code=302)

		# already on ngrok (or we can't determine hosts) -> show the real UI
		return render_template("index.html") # or whatever your main page is

	# no base set yet -> tiny "waiting" page, with no-cache headers
	html = '<h3>Waiting for ngrok…</h3><p>POST a JSON {"base":"https://…"} to /ngrok</p>'
	headers = {
		"Cache-Control": "no-store, max-age=0",
		"CDN-Cache-Control": "no-store",
		"Pragma": "no-cache",
		"Expires": "0",
	}
	return Response(html, status=503, headers=headers)

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

def load_missyou_data():
	with open('missyou.json', 'r') as f:
		return json.load(f)

def save_missyou_data(data):
	with open('missyou.json', 'w') as f:
		json.dump(data, f)

@app.route("/missyou/tap", methods=["POST"])
def tap_heart():
	data = load_missyou_data()

	if "clicks" not in data:
		data["clicks"] = 0
	if "rings" not in data:
		data["rings"] = []

	# Increment clicks first
	data["clicks"] += 1

	# Every 10 clicks, add a ring
	if data["clicks"] % 10 == 0:
		now = datetime.utcnow().isoformat()
		data["rings"].append(now)
		print(f"[💖] Ring added at {now}")

	save_missyou_data(data)

	return jsonify({
		"clicks": data["clicks"],
		"rings": len(data["rings"])
	})

@app.route("/missyou/status")
def missyou_status():
	try:
		with open("missyou.json", "r") as f:
			data = json.load(f)
		now = datetime.utcnow()
		active_rings = 0
		for ts in data.get("rings", []):
			try:
				ring_time = datetime.fromisoformat(ts.replace("Z", "").split(".")[0]) # strip microseconds/Z
			except Exception:
				continue
			elapsed = (now - ring_time).total_seconds() / 60
			if elapsed <= 30:
				active_rings += 1
		return jsonify({"active_rings": active_rings})
	except Exception as e:
		return jsonify({"error": str(e)})

@app.route("/missyou/rings", methods=["GET"])
def get_ring_timestamps():
	data = load_missyou_data()
	return jsonify(data.get("rings", []))

@app.route("/poem_override", methods=["POST"])
def poem_override():
	msg = request.form.get("override_msg", "")
	set_override_message(msg)
	return redirect("/poems")

@app.route("/favorite_poem", methods=["POST"])
def favorite_poem():
	try:
		with open("current_poem.json", "r", encoding="utf-8") as f:
			current_poem = json.load(f)

		with open("poems.json", "r", encoding="utf-8") as f:
			poem_data = json.load(f)

		# Move to favorites if not already there
		if current_poem not in poem_data.get("favorites", []):
			poem_data["favorites"].append(current_poem)

		with open("poems.json", "w", encoding="utf-8") as f:
			json.dump(poem_data, f, indent=4)

		return redirect("https://smartmirror-app.onrender.com/poems")
	except Exception as e:
		return f"Error favoriting poem: {e}", 500

@app.route("/remove_poem", methods=["POST"])
def remove_poem():
	try:
		with open("current_poem.json", "r", encoding="utf-8") as f:
			current_poem = json.load(f)

		with open("poems.json", "r", encoding="utf-8") as f:
			poem_data = json.load(f)

		# Move to removed if not already there
		if current_poem not in poem_data.get("removed", []):
			poem_data["removed"].append(current_poem)

		# Remove from display pool
		if current_poem in poem_data.get("display", []):
			poem_data["display"].remove(current_poem)

		with open("poems.json", "w", encoding="utf-8") as f:
			json.dump(poem_data, f, indent=4)

		return redirect("https://smartmirror-app.onrender.com/poems")
	except Exception as e:
		return f"Error removing poem: {e}", 500

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

# ---- NGROK SYNC (store the live public URL on Render) ----

def _read_ngrok_file():
	try:
		with open(NGROK_FILE, "r", encoding="utf-8") as f:
			return json.load(f)
	except Exception:
		return {}

@app.route("/ngrok", methods=["GET", "POST"])
def ngrok_route():
	if request.method == "POST":
		data = request.get_json(silent=True) or {}
		base = (data.get("base") or "").strip().rstrip("/")
		if not (base.startswith("http://") or base.startswith("https://")):
			return jsonify({"error": "invalid base"}), 400
		with open(NGROK_FILE, "w", encoding="utf-8") as f:
			json.dump({"base": base, "updated_at": datetime.utcnow().isoformat() + "Z"}, f)
		return jsonify({"status": "ok"})

	# GET
	try:
		with open(NGROK_FILE, "r", encoding="utf-8") as f:
			payload = json.load(f)
	except Exception:
		payload = {}

	# prevent stale CDN/browser caches
	headers = {
		"Cache-Control": "no-store, max-age=0",
		"CDN-Cache-Control": "no-store",
		"Pragma": "no-cache",
		"Expires": "0",
	}
	return make_response(jsonify(payload), 200, headers)


if __name__ == "__main__":
	app.run(host="0.0.0.0", port=5000)
