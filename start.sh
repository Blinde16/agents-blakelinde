#!/usr/bin/env bash
set -e

echo "=> Activating OpenClaw Environment for Blake Linde"

# 1. Python Environment Setup for Skills
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
fi

echo "Installing Skill Dependencies..."
source .venv/bin/activate
pip install -r requirements.txt -q

# 2. Check for API keys
if [ ! -f ".env" ]; then
    echo "Error: .env file missing. Run setup first."
    exit 1
fi

if ! grep -q "SLACK_BOT_TOKEN=" .env || ! grep -q "SLACK_APP_TOKEN=" .env; then
    echo "Warning: Slack tokens not found in .env. Interactive prompt mode will be used."
fi

# 3. Fire up OpenClaw
echo "=> Starting OpenClaw Daemon..."
npx openclaw@latest start --daemon
echo "=> OpenClaw is now running in the background! Logs are available via 'npx openclaw logs'."
