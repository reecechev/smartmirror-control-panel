import os
import requests

RENDER_NGROK_URL = "https://smartmirror-control-panel.onrender.com/ngrok"
GIST_FALLBACK_URL = "https://gist.githubusercontent.com/reecechev/27cac807fe63cc098a10e454427063907/raw/smartmirror-link.txt"

def _strip(u: str) -> str:
	return u.strip().rstrip("/")

def get_ngrok_url() -> str:
	# 1) Try Render (/ngrok returns {"base": "https://....ngrok-free.app"})
	try:
		r = requests.get(RENDER_NGROK_URL, timeout=4)
		if r.ok:
			base = (r.json() or {}).get("base")
			if base:
				return _strip(base)
	except Exception:
		pass

	# 2) Optional env override (handy for testing)
	env = os.getenv("SMARTMIRROR_BASE")
	if env:
		return _strip(env)

	# 3) Fallback to the Gist (legacy)
	try:
		r = requests.get(GIST_FALLBACK_URL, timeout=4)
		if r.ok and r.text.strip():
			return _strip(r.text)
	except Exception:
		pass

	# 4) If everything failed, raise a clear error
	raise RuntimeError("Could not resolve ngrok base URL (Render /ngrok, env, or Gist).")
