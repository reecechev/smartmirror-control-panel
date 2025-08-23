import os, requests

RENDER_NGROK_ENDPOINT = os.environ.get(
	"RENDER_NGROK_ENDPOINT",
	"https://smartmirror-control-panel.onrender.com/ngrok"
)

def get_ngrok_url():
	# 1) Ask Render for the current public base
	try:
		r = requests.get(RENDER_NGROK_ENDPOINT, timeout=4)
		r.raise_for_status()
		data = r.json()
		base = str(data.get("base", "")).rstrip("/")
		if base.startswith("http"):
			return base
	except Exception:
		pass

	# 2) Final fallback: env var on the Pi (optional)
	env_base = os.environ.get("SMARTMIRROR_BASE", "").rstrip("/")
	if env_base:
		return env_base

	raise RuntimeError("Could not resolve ngrok base (Render /ngrok or env).")
