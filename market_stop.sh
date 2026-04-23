#!/bin/bash
# Stops the trading bot at market close

LOG="$HOME/jarvis_market.log"
PIDFILE="$HOME/jarvis_bot.pid"

echo "[$(date)] Stopping trading bot at market close..." >> "$LOG"

if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    kill "$PID" 2>/dev/null
    rm -f "$PIDFILE"
    echo "[$(date)] Bot stopped (PID=$PID)." >> "$LOG"
    echo "Bot stopped."
else
    echo "[$(date)] No PID file found, bot may not be running." >> "$LOG"
    echo "Bot was not running."
fi
