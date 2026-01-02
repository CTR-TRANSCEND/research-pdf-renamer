#!/bin/bash

# Research PDF File Renamer - Stop Script
# This script ONLY stops the Flask application running on port 5000
# It will NOT affect other Python services on different ports (e.g., 8000, 8080)

# Configuration
PORT=5000
APP_NAME="Research PDF File Renamer"

echo "========================================"
echo "Stopping $APP_NAME (Port $PORT only)"
echo "========================================"

# Find processes running on port 5000
PIDS=$(lsof -ti:$PORT 2>/dev/null)

if [ -z "$PIDS" ]; then
    echo "No process found running on port $PORT."
    echo "The application may already be stopped."
    exit 0
fi

# Show what will be stopped
echo "Found the following process(es) on port $PORT:"
echo ""
for PID in $PIDS; do
    ps -p $PID -o pid,ppid,user,command 2>/dev/null | tail -n +2
done
echo ""

# Confirm before stopping
read -p "Stop these process(es)? (y/n): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Stopping process(es) on port $PORT..."

    # Try graceful shutdown first (SIGTERM)
    for PID in $PIDS; do
        kill $PID 2>/dev/null
    done

    # Wait a moment for graceful shutdown
    sleep 2

    # Check if still running, force kill if necessary
    REMAINING=$(lsof -ti:$PORT 2>/dev/null)
    if [ -n "$REMAINING" ]; then
        echo "Process still running, sending SIGKILL..."
        for PID in $REMAINING; do
            kill -9 $PID 2>/dev/null
        done
        sleep 1
    fi

    # Verify stopped
    if lsof -ti:$PORT > /dev/null 2>&1; then
        echo "ERROR: Failed to stop process on port $PORT"
        exit 1
    else
        echo "Successfully stopped $APP_NAME on port $PORT."
    fi
else
    echo "Aborted. No processes were stopped."
    exit 0
fi

echo ""
echo "Note: Other Python services (ports 8000, 8080, etc.) were NOT affected."
