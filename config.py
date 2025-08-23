import os, json, urllib.request

def _http_get_json(url, timeout=5):
	with urllib.request.urlopen(url, timeout=timeout) as r:
		return json.load(r)

def get_ngrok_url():
	# 1) local Flask file (/ngrok served from ngrok.json)
	try:
		data = _http_get_json("http://127.0.0.1:5000/ngrok", timeout=2)
		base = str(data.get("base", "")).strip().rstrip("/")
		if base.startswith("http"):
			return base
	except Exception:
		pass

	# 2) Render (public, might be sleeping, but updater wakes it)
	try:
		data = _http_get_json("https://smartmirror-control-panel.onrender.com/ngrok", timeout=5)
		base = str(data.get("base", "")).strip().rstrip("/")
		if base.startswith("http"):
			return base
	except Exception:
		pass

	# 3) Env fallback (optional)
	base = os.environ.get("SMARTMIRROR_BASE", "").strip().rstrip("/")
	if base.startswith("http"):
		return base

	raise RuntimeError("Could not resolve ngrok base (Render /ngrok or env).")
