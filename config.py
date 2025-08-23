import os, requests

RENDER_NGROK_ENDPOINT = "https://smartmirror-control-panel.onrender.com/ngrok"
GIST_RAW_URL = "https://gist.githubusercontent.com/reececheev/27acb0f7638cca981a10e454427063907/raw/smartmirror-link.txt"

def _clean(u: str) -> str:
	return (u or "").strip().rstrip("/")

def get_ngrok_url():
	# 1) Render (authoritative)
	try:
		r = requests.get(RENDER_NGROK_ENDPOINT, timeout=5)
		if r.ok:
			base = _clean(r.json().get("base", ""))
			if base:
				return base
	except Exception:
		pass

	# 2) Environment fallback (works on Pi or Render)
	env_base = _clean(os.environ.get("SMARTMIRROR_BASE", ""))
	if env_base:
		return env_base

	# 3) Gist fallback
	try:
		r = requests.get(GIST_RAW_URL, timeout=5)
		if r.ok:
			base = _clean(r.text)
			if base:
				return base
	except Exception:
		pass

	raise RuntimeError("Could not resolve ngrok base URL (Render /ngrok, env, or Gist).")
