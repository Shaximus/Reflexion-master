#!/bin/bash
# REFLEXION SHIELD -- War Room Launcher
# Usage: ./warroom.sh [--quick-status]

cd /home/shax/Projects/core-tech/Reflexion-master

# Activate venv if present
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

python3 src/dashboard.py "$@"
