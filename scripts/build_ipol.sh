#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PNG_FLAGS=()
PNG_LIBS=()
if command -v pkg-config >/dev/null && pkg-config --exists libpng; then
  read -r -a PNG_FLAGS <<< "$(pkg-config --cflags libpng)"
  read -r -a PNG_LIBS <<< "$(pkg-config --libs libpng)"
elif [[ -f /opt/homebrew/include/png.h ]]; then
  PNG_FLAGS=(-I/opt/homebrew/include)
  PNG_LIBS=(-L/opt/homebrew/lib -lpng)
else
  PNG_LIBS=(-lpng)
fi
make -C "$ROOT/third_party/ipol" CXX="${CXX:-c++}" "CFLAGS=-O3 -std=c++98 ${PNG_FLAGS[*]}" "LDFLAGS=${PNG_LIBS[*]} -lm"
