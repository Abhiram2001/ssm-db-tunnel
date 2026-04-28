#!/bin/bash
# start.sh — Development launcher for SsmDbTunnel
#
# For production/distribution, use scripts/build_macos.sh instead.

set -euo pipefail

# Always run from the project root regardless of where this script is invoked
cd "$(dirname "$0")/.."

echo "Starting SsmDbTunnel (dev mode)..."
echo ""

# ---- Virtual environment ----------------------------------------------------
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    echo ""
fi

source .venv/bin/activate

# ---- Install / sync dependencies --------------------------------------------
if ! python -c "import flask, rumps, pymysql, bleach, dotenv" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install -r requirements-dev.txt
    echo ""
fi

# ---- Runtime checks ---------------------------------------------------------
if ! command -v aws &>/dev/null; then
    echo "WARNING: AWS CLI not found. Install with: brew install awscli"
    echo ""
fi

echo "Starting on a dynamically assigned port (browser will open automatically)"
echo "Menu-bar icon: database cylinder — use it to stop sessions or quit."
echo ""
python launcher.py
