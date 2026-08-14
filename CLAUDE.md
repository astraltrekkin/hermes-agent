# Hermes Agent — Claude Code notes

## Cloud sessions (`claude --cloud` / claude.ai/code)

SessionStart runs `.claude/scripts/cloud_session_setup.sh` when `CLAUDE_CODE_REMOTE=true`.
That installs Python deps via `uv sync` and optional npm packages. Do **not**
`STATUS: hard_stop` for missing deps until that script has been run (or re-run)
and still fails — paste the script output if blocked.

- Python: use `uv` / the project venv from `uv sync` (requires Python >=3.11,<3.14).
- Node: cloud VMs provide Node 22+ on PATH (project engines: `>=22.22.0`).
- Prefer reproducing bugs before implementing fixes.
- Push only to the work fork branch; do not open upstream PRs or post issue comments unless asked.

## Local sessions

The SessionStart script no-ops unless `CLAUDE_CODE_REMOTE=true`. Follow `CONTRIBUTING.md` / `AGENTS.md` for local setup.
