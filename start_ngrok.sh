#!/usr/bin/env bash

nohup ngrok http 5000 --log+stdout > /home/pi/smartmirror/ngrok.log 2>&1 &
