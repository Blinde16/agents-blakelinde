#!/bin/bash
set -e

echo "=> Bootstrapping OpenClaw config..."

# Set gateway to local mode (satisfies the missing config check)
openclaw config set gateway.mode local 2>/dev/null || true

# Required when binding to non-loopback (--bind lan): satisfy Control UI origin check
openclaw config set gateway.controlUi.dangerouslyAllowHostHeaderOriginFallback true 2>/dev/null || true

# Register Slack channel from env vars if tokens are present
if [ -n "$SLACK_BOT_TOKEN" ] && [ -n "$SLACK_APP_TOKEN" ]; then
    echo "=> Registering Slack channel..."
    openclaw channels add \
        --channel slack \
        --bot-token "$SLACK_BOT_TOKEN" \
        --app-token "$SLACK_APP_TOKEN" \
        2>/dev/null || true
    echo "=> Slack channel registered."
else
    echo "=> WARNING: SLACK_BOT_TOKEN or SLACK_APP_TOKEN not set. Slack will not connect."
fi

echo "=> Starting OpenClaw gateway..."
exec openclaw gateway --bind lan
