#!/bin/bash

# Ensure we are in the project root
cd "$(dirname "$0")"

# Set the master key for both processes
export SERVER_MASTER_KEY="super_secret_master_key_2025"

echo "Starting Ticker Service..."
export PYTHONPATH=$PYTHONPATH:.
./.venv/bin/python src/ticker.py &
TICKER_PID=$!

echo "Starting Web Server..."
./.venv/bin/python src/app.py &
SERVER_PID=$!

echo "Services started."
echo "Ticker PID: $TICKER_PID"
echo "Server PID: $SERVER_PID"
echo "Press Ctrl+C to stop both services."

# Wait for user to press Ctrl+C
trap "kill $TICKER_PID $SERVER_PID; exit" SIGINT SIGTERM
wait
