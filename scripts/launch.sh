#!/bin/bash
# Reflexion Launch Script
# Starts the daemon with proper environment

echo "Launching Reflexion Swarm..."

# Check environment
if [ ! -f .env ]; then
    echo "[ERROR] .env file not found!"
    exit 1
fi

# Source environment
export $(cat .env | grep -v '^#' | xargs)

# Launch daemon
python reflexion_daemon_prod.py

echo "Reflexion shutdown complete"
