# Node 22 (LTS) as base — openclaw is a Node process
FROM node:22-slim

# Install Python 3 + pip for skills runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency files first (layer cache)
COPY requirements.txt ./

# Install Python skill dependencies
RUN python3 -m pip install --no-cache-dir --break-system-packages -r requirements.txt

# Copy the rest of the repo
COPY . .

# openclaw is invoked via npx — no npm install needed
# Expose nothing: this is a WebSocket worker, not an HTTP server

CMD ["npx", "--yes", "openclaw", "gateway", "--bind", "lan", "--force"]
