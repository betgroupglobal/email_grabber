#!/bin/bash

# Script to run the WebSocket server for real-time dashboard updates

cd "$(dirname "$0")"

echo "Starting WebSocket server for AutonomAI dashboard..."
echo "WebSocket server will run on ws://localhost:3001"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Install websockets if not already installed
pip install websockets==12.0

# Run the WebSocket server
python websocket_server.py