from flask import Flask, request, jsonify, render_template
from flask import Flask, render_template, request, redirect, make_response
import json
from flask_cors import CORS
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
	return render_template("index.html")

REMINDERS_FILE = "reminders.json"
POEMS_FILE = "poems.json"
OVERRIDE_FILE = "poem_override.json"

def load_reminders():
	try:
		with open(REMINDERS_FILE, "r") as f:
			return json.load(f)
	except FileNotFoundError:
		return []

def save_reminders(reminders):
	with open(REMINDERS_FILE, "w") as f:
		json.dump(reminders, f)

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

@app.route("/add_poem", methods=["GET", "POST"])
def add_poem():
	poems = load_poems()
	new_poem = {
		"text": request.form["poem_text"],
		"favorite": "is_favorite" in request.form
	}
	poems.append(new_poem)
	save_poems(poems)
	return redirect("/poems")


def load_poems():
	try: 
		with open(POEMS_FILE, "r") as f:
			return json.load(f)
	except:
		return []

def save_poems(poems):
	with open(POEMS_FILE, "w") as f:
		json.dump(poems, f)

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

@app.route("/missyou/status", methods=["GET"])
def get_active_rings():
	data = load_missyou_data()
	now = datetime.utcnow()
	valid_rings = [
		r for r in data.get('rings', [])
		if now - datetime.fromisoformat(r) < timedelta(minutes=30)
	]
	return jsonify({'active_rings': len(valid_rings)})

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

if __name__ == "__main__":
	app.run(host="0.0.0.0", port=5000)
