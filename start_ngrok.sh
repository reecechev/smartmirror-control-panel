#!/usr/bin/env bash
set -euo pipefail

# Wait for Flask to be listening (any status is fine)
until curl -s http://127.0.0.1:5000/ -o /dev/null; do sleep 1; done

# Kill any old ngrok for port 5000
pkill -f "ngrok http 5000" 2>/dev/null || true

# Start ngrok fully detached, with a guaranteed path + logs
NGROK_BIN="$(command -v ngrok || true)"
[ -n "$NGROK_BIN" ] || { echo "ERROR: ngrok not in PATH"; exit 1; }
nohup "$NGROK_BIN" http 5000 --log=stdout --log-level=info \
	>> /home/pi/smartmirror/ngrok.log 2>&1 < /dev/null &

echo $! > /home/pi/smartmirror/ngrok.pid
