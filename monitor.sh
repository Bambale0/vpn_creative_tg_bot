#!/bin/bash
PID_FILE="/var/run/wg-bot.pid"
LOG="/var/log/vpn/monitor.log"
SCRIPT_DIR="/root/newvpn"

if [[ ! -f $PID_FILE ]] || [[ ! -d /proc/$(cat $PID_FILE) ]]; then
    echo "[$(date)] Bot not running, restarting..." >> $LOG

    cd "$SCRIPT_DIR"
    nohup python3 bot.py >> server.log 2>&1 &
    echo $! > $PID_FILE

    echo "[$(date)] Bot restarted" >> $LOG
fi
