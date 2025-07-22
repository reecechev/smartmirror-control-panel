import requests

def get_ngrok_url():
	url = "https://gist.githubusercontent.com/reecechev/27cac80f7e63cc98a10e454427063907/raw/smartmirror-link.txt"
	response = requests.get(url)
	return response.text.strip()
