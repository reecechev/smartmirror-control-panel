#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/home/pi/smartmirror"
VENV_PY="$APP_DIR/venv/bin/python3"
NGROK_BIN="/usr/local/bin/ngrok"
LOG_APP="$APP_DIR/app.log"
LOG_NGROK="$APP_DIR/ngrok.log"

cd "$APP_DIR"

# 0) Clean up anything old (harmless if nothing running)
pkill -f "python3 app.py" >/dev/null 2>&1 || true
pkill -f "ngrok http 5000" >/dev/null 2>&1 || true

# 1) Start Flask (use the VENV Python) and log to file
nohup "$VENV_PY" app.py >>"$LOG_APP" 2>&1 &

# 2) Wait up to 30s for Flask to answer on 127.0.0.1:5000
for i in {1..30}; do
    if curl -fsS http://127.0.0.1:5000/ >/dev/null; then
        break
    fi
    sleep 1
done

# If still not up, bail (systemd will show failure and restart on boot)
curl -fsS http://127.0.0.1:5000/ >/dev/null

# 3) Start ngrok on IPv4 localhost:5000 and log
nohup "$NGROK_BIN" http http://127.0.0.1:5000 --log=stdout --log-level=info >>"$LOG_NGROK" 2>&1 &

# 4) Push the fresh URL to Render (no strict dependency; don’t fail boot on this)
bash "$APP_DIR/update_ngrok.sh" || true
