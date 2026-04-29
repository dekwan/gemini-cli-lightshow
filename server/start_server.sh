#!/bin/bash

# Exit on error
set -e

# Get the directory where the script is located
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
VENV_DIR="$SCRIPT_DIR/.venv"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"
SERVER_SCRIPT="$SCRIPT_DIR/server.py"

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment in $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
fi

# Activate the virtual environment
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Check if requirements.txt exists
if [ ! -f "$REQUIREMENTS_FILE" ]; then
    echo "Error: $REQUIREMENTS_FILE not found."
    exit 1
fi

# Install dependencies from the virtual environment
# Try pip first, if it fails, try uv
echo "Attempting to install dependencies using pip..."
python -m pip install -r "$REQUIREMENTS_FILE" || {
    echo "pip installation failed, trying uv..."
    uv pip install -r "$REQUIREMENTS_FILE"
}

# Run the MCP server using the venv python
echo "Starting MCP Server from $SERVER_SCRIPT..."
exec python "$SERVER_SCRIPT"
