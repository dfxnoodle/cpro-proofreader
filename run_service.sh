#!/usr/bin/env bash
#
# CPro-Proofreader – FastAPI via gunicorn/uv (Unix-socket edition)

set -euo pipefail

cd /home/dinochlai/cpro-proofreader               # ← project root

# ── 1. Load secrets (.env is optional) ────────────────────────────────────────
if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  source .env
else
  echo "⚠️  .env not found – continuing with existing env" | logger -t cpro-proofreader
fi

export AZURE_OPENAI_ENDPOINT AZURE_OPENAI_API_KEY \
       AZURE_OPENAI_DEPLOYMENT_NAME AZURE_OPENAI_API_VERSION

# ── 2. Pick socket path (or fall back to TCP if PORT is set) ──────────────────
SOCKET_PATH=${SOCKET_PATH:-/run/cpro-proofreader/cpro.sock}
if [[ -n "${PORT:-}" ]]; then
  BIND="0.0.0.0:${PORT}"
  logger -t cpro-proofreader "starting on TCP ${BIND}"
else
  BIND="unix:${SOCKET_PATH}"
  logger -t cpro-proofreader "starting on socket ${SOCKET_PATH}"
fi

# ── 3. Ensure uv is in PATH (installs once, then re-used) ─────────────────────
PATH="$HOME/.local/bin:$PATH"
if ! command -v uv &>/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# ── 4. Sync deps (fast - uses lockfile) and launch gunicorn -─────────────────
uv sync  >/dev/null
exec uv run gunicorn main:app \
        --workers "${WORKERS:-4}" \
        --worker-class uvicorn.workers.UvicornWorker \
        --bind "${BIND}"
