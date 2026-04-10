#!/bin/bash
set -e

echo "=> Bootstrapping OpenClaw config..."

# Set gateway to local mode (satisfies the missing config check)
openclaw config set gateway.mode local 2>/dev/null || true

# Required when binding to non-loopback (--bind lan): satisfy Control UI origin check
openclaw config set gateway.controlUi.dangerouslyAllowHostHeaderOriginFallback true 2>/dev/null || true

# Force model config by writing directly to openclaw.json via Python
python3 - <<PYEOF
import json, os
config_path = os.path.expanduser("~/.openclaw/openclaw.json")
try:
    with open(config_path) as f:
        config = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    config = {}
config["llm"] = {
    "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
    "routerModel": os.environ.get("OPENAI_ROUTER_MODEL", "gpt-4o-mini"),
    "embeddingModel": os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
}
os.makedirs(os.path.dirname(config_path), exist_ok=True)
with open(config_path, "w") as f:
    json.dump(config, f, indent=2)
print("=> LLM model config written:", config["llm"])
PYEOF

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
