#!/usr/bin/env python3
import json, os, sys, time, urllib.request

RENDER_ENDPOINT = "https://smartmirror-control-panel.onrender.com/ngrok"
LOCAL_FILE = "/home/pi/smartmirror/ngrok.json"

def get_public_url():
	# Wait for ngrok API to be ready (up to ~20s)
	for _ in range(20):
		try:
			with urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=2) as r:
				data = json.load(r)
			break
		except Exception:
			time.sleep(1)
	else:
		raise RuntimeError("ngrok API not available")

	for t in data.get("tunnels", []):
		u = t.get("public_url", "")
		if u.startswith("https://"):
			return u
	raise RuntimeError("No https tunnel found")

def save_local(base):
	payload = {"base": base, "status": "ok", "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
	tmp = LOCAL_FILE + ".tmp"
	with open(tmp, "w", encoding="utf-8") as f:
		json.dump(payload, f, ensure_ascii=False, indent=2)
	os.replace(tmp, LOCAL_FILE)
	print(f"Updated local Flask: {payload}")

def post_render(base, max_wait=120):
	# Wake Render by hitting '/', then POST /ngrok with retries
	start = time.time()

def http_get(url, timeout=4):
	try:
		with urllib.request.urlopen(url, timeout=timeout) as r:
			return r.status
	except Exception:
		return None

	# Try to wake up the app
	while time.time() - start < max_wait:
		code = http_get(RENDER_ENDPOINT.rsplit("/", 1)[0] + "/", timeout=4)
		if code and 200 <= code < 500: # any non-5xx likely means it's awake
			break
		time.sleep(3)

	payload = json.dumps({"base": base}).encode("utf-8")
	req = urllib.request.Request(
		RENDER_ENDPOINT,
		data=payload,
		headers={"Content-Type": "application/json"},
		method="POST",
	)

	delay = 2
	while time.time() - start < max_wait:
		try:
			with urllib.request.urlopen(req, timeout=6) as r:
				if 200 <= r.status < 300:
					print("Posted to Render OK.")
					return True
				else:
					print("Render POST status:", r.status)
		except Exception as e:
			print("Render POST error:", e)
		time.sleep(delay)
		delay = min(delay * 1.7, 15)

	print("WARN: Render update failed after retries.")
	return False

def main():
	base = get_public_url()
	print("Public URL:", base)
	save_local(base)
	post_render(base)

if __name__ == "__main__":
	main()
