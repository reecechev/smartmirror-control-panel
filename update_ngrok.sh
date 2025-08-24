#!/usr/bin/env bash
set -euo pipefail

API="http://127.0.0.1:4040/api/tunnels"
RENDER="https://smartmirror-control-panel.onrender.com/ngrok"
LOG="/home/pi/smartmirror/ngrok_update.log"

# 1) Get the https public_url
BASE=$(curl -s "$API" | jq -r '.tunnels[]?.public_url | select(startswith("https://"))' | head -n1)

if [[ -z "$BASE" ]]; then
	echo "ERR: no https public_url from ngrok API" | tee -a "$LOG"
	exit 2
fi

# 2) Save to ngrok.json locally
echo "{\"base\": \"$BASE\", \"status\": \"ok\", \"updated_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" \
	| tee /home/pi/smartmirror/ngrok.json | tee -a "$LOG"

# 3) Wake Render app (ignore errors)
curl -fsS "$RENDER" >/dev/null || true

# 4) Push to Render
curl -fsS -X POST "$RENDER" \
	-H "Content-Type: application/json" \
	-d "{\"base\":\"$BASE\"}" | tee -a "$LOG"
