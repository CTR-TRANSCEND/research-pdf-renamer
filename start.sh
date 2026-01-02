#!/bin/bash

# Research PDF File Renamer - Start Script
# This script starts the Flask application on port 5000

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
PORT=5000
APP_NAME="Research PDF File Renamer"

echo "========================================"
echo "Starting $APP_NAME"
echo "========================================"

# Check if port is already in use
if lsof -ti:$PORT > /dev/null 2>&1; then
    echo "Warning: Port $PORT is already in use."
    echo "Existing process(es) on port $PORT:"
    lsof -ti:$PORT | xargs -I {} ps -p {} -o pid,command 2>/dev/null
    echo ""
    read -p "Do you want to stop the existing process and start fresh? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Stopping existing process on port $PORT..."
        lsof -ti:$PORT | xargs -r kill 2>/dev/null
        sleep 2
    else
        echo "Aborted. Please stop the existing service first."
        exit 1
    fi
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
else
    echo "Warning: No virtual environment found. Using system Python."
fi

# Start the application
echo "Starting application on port $PORT..."
python run.py
