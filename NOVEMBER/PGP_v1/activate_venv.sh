#!/bin/bash
# Quick activation script for PGP_v1 virtual environment
# Usage: source activate_venv.sh

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_PATH="${SCRIPT_DIR}/.venv"

if [ ! -d "$VENV_PATH" ]; then
    echo "❌ Virtual environment not found at: $VENV_PATH"
    echo "Run ./setup_venv.sh first to create it"
    return 1
fi

source "$VENV_PATH/bin/activate"
echo "✅ Virtual environment activated: $VENV_PATH"
echo "🐍 Python: $(which python)"
echo "📦 Python version: $(python --version)"
