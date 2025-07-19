import requests
from flask import Flask, redirect
import time

app = Flask(__name__)

# GitHub Gist raw URL to your smartmirror-link.txt
GIST_URL = "https://gist.githubusercontent.com/reecechev/27cac80f7e63cc98a10e454427063907/raw/6b48a3b1bf93345e9821037df3e739a993b8e9b1/smartmirror-link.txt"

def get_latest_ngrok_url():
  try:
    response = requests.get(GIST_URL, timeout=5)
    if response.status_code == 200:
      return response.text.strip()
  except Exception as e:
    print("Error fetching ngrok URL:", e)
  return None

@app.route("/")
def redirect_to_ngrok():
  url = get_latest_ngrok_url()
  if url:
    return redirect(url, code=302)
  return "Ngrok URL not available", 503

if __name__ == "__main__":
app.run(debug=True)
