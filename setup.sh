#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  printf '%s\n' "Python executable not found: $PYTHON" >&2
  exit 1
fi
if ! command -v node >/dev/null 2>&1; then
  printf '%s\n' 'Node.js 22+ is required.' >&2
  exit 1
fi
if ! command -v pnpm >/dev/null 2>&1; then
  printf '%s\n' 'pnpm is required.' >&2
  exit 1
fi

if [[ ! -d "$ROOT/.venv" ]]; then
  "$PYTHON" -m venv "$ROOT/.venv"
fi
"$ROOT/.venv/bin/python" -m pip install --upgrade pip
"$ROOT/.venv/bin/python" -m pip install -r "$ROOT/backend/requirements-lock.txt"

pnpm --dir "$ROOT/frontend" install --frozen-lockfile
bash "$ROOT/scripts/build_ipol.sh"
pnpm --dir "$ROOT/frontend" run build

printf '%s\n' 'StraightLens is ready. Start it with: bash scripts/run_local.sh'
