#!/usr/bin/env bash
set -euo pipefail

# Optional first arg overrides NODE_PORT to match registry submodule scripts.
CLI_PORT="${1:-}"

# Ensure we are at the project root where the node entrypoint and pyproject live.
if [[ ! -f "pyproject.toml" || ! -f "src/node/main.py" ]]; then
  echo "Run this script from the repository root (pyproject.toml and src/node/main.py not found)." >&2
  exit 1
fi

# Align with registry submodules: require uv and install deps if lock/venv missing.
if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required to run the node locally. Install uv: https://docs.astral.sh/uv/." >&2
  exit 1
fi

if [[ ! -d ".venv" || ! -f "uv.lock" ]]; then
  echo "Installing dependencies with uv sync..."
  uv sync
fi

# Defaults align with compose.yml and registry expectations.
: "${NODE_NAME:=droq-node-template}"
: "${NODE_PORT:=${CLI_PORT:-8000}}"
: "${LOG_LEVEL:=INFO}"
: "${NATS_URL:=nats://localhost:4222}"
: "${NATS_CLIENT_NAME:=$NODE_NAME}"
: "${STREAM_NAME:=droq-stream}"

export NODE_NAME NODE_PORT LOG_LEVEL NATS_URL NATS_CLIENT_NAME STREAM_NAME
export PYTHONPATH="${PYTHONPATH:-src}"

echo "Starting Droq node locally with:"
echo "  NODE_NAME=${NODE_NAME}"
echo "  NODE_PORT=${NODE_PORT}"
echo "  LOG_LEVEL=${LOG_LEVEL}"
echo "  NATS_URL=${NATS_URL}"
echo "  STREAM_NAME=${STREAM_NAME}"
echo

# Use uv to run main just like registry node submodules.
uv run python -m node.main "${@:2}"
