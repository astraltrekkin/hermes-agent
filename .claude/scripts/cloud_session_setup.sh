#!/usr/bin/env bash
# Claude Code cloud SessionStart: install hermes deps on Anthropic-hosted VMs only.
# See https://code.claude.com/docs/en/cloud-environments#install-dependencies-with-a-sessionstart-hook
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$ROOT"

export PATH="${HOME}/.local/bin:/usr/local/bin:${PATH}"
export UV_LINK_MODE="${UV_LINK_MODE:-copy}"

echo "[cloud_session_setup] project=${ROOT}"
echo "[cloud_session_setup] python=$(command -v python3 || true) node=$(command -v node || true) uv=$(command -v uv || true)"

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="${HOME}/.local/bin:${PATH}"
fi

# Python toolchain + locked deps (hermes requires >=3.11,<3.14)
if [ -f uv.lock ]; then
  uv sync --frozen
else
  uv sync
fi

# Optional Node workspace (engines: node >=22). Cloud VMs ship Node 22 on PATH.
if [ -f package.json ]; then
  if [ -f package-lock.json ]; then
    npm ci --ignore-scripts || npm install --ignore-scripts
  else
    npm install --ignore-scripts
  fi
fi

# Persist PATH for later Bash tool calls in this session
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  {
    echo "export PATH=\"${HOME}/.local/bin:\${PATH}\""
    echo "export UV_LINK_MODE=copy"
  } >> "$CLAUDE_ENV_FILE"
fi

echo "[cloud_session_setup] done"
