# Node 22 (LTS) as base — openclaw is a Node process
FROM node:22-slim

# Install Python 3 + pip for skills runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Pre-install openclaw globally at build time — avoids 4-min runtime download
RUN npm install -g openclaw

# Copy dependency files first (layer cache)
COPY requirements.txt ./

# Install Python skill dependencies
RUN python3 -m pip install --no-cache-dir --break-system-packages -r requirements.txt

# Copy repo
COPY . .

# Run the pre-installed binary directly — no npx download on startup
CMD ["openclaw", "gateway", "--bind", "lan"]
