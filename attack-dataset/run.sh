#!/bin/bash
cd /Users/adminuser/attack-dataset

# Kill existing
lsof -ti:8001,8010,8500,3001,3000 | xargs kill -9 2>/dev/null
pkill -9 -f "python -m main" 2>/dev/null
pkill -9 -f "uvicorn" 2>/dev/null
pkill -9 -f "opsec-analyzer" 2>/dev/null
pkill -9 -f "node index.js" 2>/dev/null
sleep 2

# Start Integration Hub
cd backend/integrations
python -m main &
sleep 3

# Start Knowledge Engine  
cd ../knowledge_engine
uvicorn api:app --host 0.0.0.0 --port 8010 &
sleep 2

# Start Orchestrator
cd ../orchestrator
node index.js &
sleep 2

# Serve Dashboard
cd ../../frontend/dashboard/build
python3 -m http.server 3000 &

echo "Services started at:"
echo "  http://localhost:3000 - Dashboard"
echo "  http://localhost:3001 - Orchestrator"
echo "  http://localhost:8010 - Knowledge Engine"
echo "  http://localhost:8500 - Integration Hub"
wait
