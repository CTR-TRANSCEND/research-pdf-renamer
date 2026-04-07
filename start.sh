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
echo ""

# Check if .env file exists, if not, create from .env.example
if [ ! -f ".env" ]; then
    echo "Configuration file .env not found."
    echo "Creating .env from .env.example template..."

    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "Created .env file."

        # Check if API key needs to be set
        if grep -q "sk-your-openai-api-key-here" .env 2>/dev/null || grep -q "your-api-key-here" .env 2>/dev/null; then
            echo ""
            echo "IMPORTANT: You need to set your API key."
            echo ""
            echo "Options:"
            echo "1. Edit .env file and add your API key"
            echo "2. Set API_KEY environment variable manually"
            echo ""
            read -p "Do you want to edit .env now? (y/n): " -n 1 -r
            echo ""
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                ${EDITOR:-nano} .env
            fi
        fi
    else
        echo "Warning: .env.example not found. Creating minimal .env file..."
        cat > .env << 'EOF'
# Environment Variables for Research PDF File Renamer
# Set your API key below
API_KEY=your-api-key-here
EOF
        echo "Created minimal .env file. Please edit it to add your API key."
    fi
    echo ""
fi

# Load environment variables from .env file
if [ -f ".env" ]; then
    echo "Loading environment variables from .env..."
    # Export variables from .env, ignoring comments and empty lines
    set -a
    source <(grep -v '^#' .env | grep -v '^$' | xargs)
    set +a
    echo "Environment variables loaded."
    echo ""
fi

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

# Python environment activation
if [ -n "$CONDA_DEFAULT_ENV" ]; then
    # Already in conda environment
    echo "Using conda environment: ${CONDA_DEFAULT_ENV}"
elif [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
else
    echo "Error: No Python environment found. Run ./setup.sh first."
    exit 1
fi

# Start the application
echo "Starting application on port $PORT..."
python run.py
