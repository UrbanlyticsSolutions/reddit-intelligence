#!/bin/bash

# Kill any existing python http servers on port 8000 (simple check)
pkill -f "python -m http.server" || true

# Start Frontend Server in Background
echo "Starting local frontend server on port 8000..."
cd frontend
nohup python3 -m http.server 8000 > ../server.log 2>&1 &
SERVER_PID=$!
cd ..
echo "Server running (PID: $SERVER_PID). Access at http://localhost:8000"

# Start Automation Loop in Background
# Start Automation Server in Background
echo "Starting automation server (runs every 30 mins)..."
nohup ./venv/bin/python3 -u server.py > /dev/null 2>&1 &
AUTO_PID=$!
echo "Automation server running in background (PID: $AUTO_PID). Logs in automation.log"
