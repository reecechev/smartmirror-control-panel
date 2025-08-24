#!/usr/bin/env bash
set -euo pipefail

API="http://127.0.0.1:4040/api/tunnels"
RENDER="https://smartmirror-control-panel.onrender.com/ngrok"
LOG="/home/pi/smartmirror/ngrok_update.log"

# wait up to 20s for ngrok's https public_url
BASE=""
for i in {1..20}; do
	BASE="$(curl -fsS "$API" | jq -r '.tunnels[]?.public_url | select(startswith("https://"))' | head -n1 || true)"
	[[ -n "$BASE" ]] && break
	sleep 1
done

if [[ -z "$BASE" ]]; then
	echo "ERR: no https public_url from ngrok API" | tee -a "$LOG"
	exit 2
fi

echo "BASE=$BASE" | tee -a "$LOG"

# wake the Render app (ignore errors)
curl -fsS "$(dirname "$RENDER")/" >/dev/null || true

# push to Render
curl -fsS -X POST "$RENDER" \
	-H 'Content-Type: application/json' \
	-d "{\"base\":\"$BASE\"}" | tee -a "$LOG"
echo >> "$LOG"
