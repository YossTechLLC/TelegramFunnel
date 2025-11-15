#!/bin/bash
# Virtual Environment Setup Script for PGP_v1
# Works in both development and production (pgp-final VM) environments

set -e  # Exit on error

echo "🔧 Setting up Python virtual environment for PGP_v1..."

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_PATH="${SCRIPT_DIR}/.venv"

# Check Python version
echo "📌 Checking Python version..."
python3 --version

# Create virtual environment
if [ -d "$VENV_PATH" ]; then
    echo "⚠️  Virtual environment already exists at: $VENV_PATH"
    read -p "Do you want to recreate it? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🗑️  Removing existing venv..."
        rm -rf "$VENV_PATH"
    else
        echo "✅ Using existing venv"
        source "$VENV_PATH/bin/activate"
        python --version
        echo "📦 Virtual environment activated at: $VENV_PATH"
        exit 0
    fi
fi

echo "🏗️  Creating virtual environment at: $VENV_PATH"
python3 -m venv "$VENV_PATH"

# Activate virtual environment
echo "⚡ Activating virtual environment..."
source "$VENV_PATH/bin/activate"

# Upgrade pip
echo "📦 Upgrading pip, setuptools, and wheel..."
pip install --upgrade pip setuptools wheel

# Install core dependencies
echo "📦 Installing core Google Cloud and database packages..."
pip install \
    flask \
    google-cloud-secret-manager \
    cloud-sql-python-connector \
    pg8000 \
    psycopg2-binary \
    python-dotenv \
    google-cloud-tasks \
    google-cloud-logging

# Install additional common packages
echo "📦 Installing additional common packages..."
pip install \
    sqlalchemy \
    flask-cors \
    flask-jwt-extended \
    python-telegram-bot \
    gunicorn \
    pydantic \
    bcrypt \
    redis \
    sendgrid \
    httpx \
    pytz \
    nest-asyncio

# Show installed packages
echo ""
echo "✅ Virtual environment setup complete!"
echo "📍 Location: $VENV_PATH"
echo "🐍 Python version: $(python --version)"
echo ""
echo "📋 Installed packages:"
pip list
echo ""
echo "To activate this virtual environment, run:"
echo "  source $VENV_PATH/bin/activate"
echo ""
