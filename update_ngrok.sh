#!/usr/bin/env bash
set -euo pipefail
python3 /home/pi/smartmirror/update_ngrok.py >> /home/pi/smartmirror/ngrok_update.log 2>&1
