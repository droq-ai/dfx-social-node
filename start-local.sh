#!/bin/bash
# Start the DFX Social Executor Node locally

set -e

PORT=${1:-8007}

echo "🚀 Starting DFX Social Executor Node on port $PORT..."

# Check if uv is available
if ! command -v uv &> /dev/null; then
    echo "❌ Error: uv is not installed. Please install it first:"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Create/activate virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    uv venv
fi

# Install dependencies
echo "📦 Installing dependencies..."
uv pip install --python .venv/bin/python nats-py aiohttp pydantic fastapi uvicorn[standard] httpx python-dotenv

# Set PYTHONPATH to include src and dfx directories
export PYTHONPATH="${PYTHONPATH:-$(pwd)/src:$(pwd)/dfx}"

# Run the service directly
export NODE_PORT=$PORT
.venv/bin/python -m node.main "$PORT"

