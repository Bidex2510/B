#!/bin/bash
# Starts the trading bot during market hours
# Runs 9:20 AM - 4:10 PM ET, Monday-Friday

LOG="$HOME/jarvis_market.log"
PIDFILE="$HOME/jarvis_bot.pid"
DIR="$HOME/b"

echo "[$(date)] Starting trading bot..." >> "$LOG"

cd "$DIR" || exit 1
source jarvis-env/bin/activate

# Kill any existing instance
if [ -f "$PIDFILE" ]; then
    OLD_PID=$(cat "$PIDFILE")
    kill "$OLD_PID" 2>/dev/null
    rm -f "$PIDFILE"
fi

# Start server in background
nohup python run_server.py >> "$LOG" 2>&1 &
echo $! > "$PIDFILE"

echo "[$(date)] Bot started, PID=$(cat $PIDFILE). Dashboard at http://localhost:8000/trading" >> "$LOG"
echo "Bot started! Open http://localhost:8000/trading"
