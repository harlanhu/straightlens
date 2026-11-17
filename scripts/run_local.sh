#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEFAULT_PYTHON="$ROOT/.venv/bin/python"
if [[ -x "$ROOT/.venv-local/bin/python" ]]; then
  DEFAULT_PYTHON="$ROOT/.venv-local/bin/python"
fi
PYTHON="${STRAIGHTLENS_PYTHON:-${LENSLINE_PYTHON:-$DEFAULT_PYTHON}}"
if [[ ! -x "$PYTHON" ]]; then
  printf '%s\n' 'Python 环境未安装。请先按 README 完成环境安装。' >&2
  exit 1
fi
if [[ ! -x "$ROOT/third_party/ipol/lens_distortion_correction_2p_iterative_optimization" ]]; then
  bash "$ROOT/scripts/build_ipol.sh"
fi
if [[ ! -f "$ROOT/frontend/dist/index.html" ]]; then
  printf '%s\n' '请先在 frontend 目录执行 pnpm install 与 pnpm run build。' >&2
  exit 1
fi
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
export STRAIGHTLENS_DATA="${STRAIGHTLENS_DATA:-${LENSLINE_DATA:-$ROOT/.runtime/jobs}}"
exec "$PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-8765}"
