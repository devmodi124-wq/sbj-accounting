#!/usr/bin/env bash
# Build & install the sqlcipher3 Python binding against Homebrew's sqlcipher.
# Usage: scripts/install_sqlcipher.sh [path-to-python]   (defaults to .venv/bin/python)
set -euo pipefail

PY="${1:-.venv/bin/python}"

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is required (https://brew.sh). On Windows, sqlcipher3 is handled differently in CI." >&2
  exit 1
fi

brew list sqlcipher >/dev/null 2>&1 || brew install sqlcipher

SQLC="$(brew --prefix sqlcipher)"
SSL="$(brew --prefix openssl@3)"

export PKG_CONFIG_PATH="$SQLC/lib/pkgconfig:$SSL/lib/pkgconfig"
export C_INCLUDE_PATH="$SQLC/include:$SQLC/include/sqlcipher"
export LIBRARY_PATH="$SQLC/lib"
export LDFLAGS="-L$SQLC/lib -L$SSL/lib"
export CPPFLAGS="-I$SQLC/include -I$SQLC/include/sqlcipher -I$SSL/include"

"$PY" -m pip install --no-binary :all: sqlcipher3
echo "sqlcipher3 installed for $PY"
