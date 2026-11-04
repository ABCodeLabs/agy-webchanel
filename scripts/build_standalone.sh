#!/usr/bin/env bash
# Standalone Nuitka build & license bundling script for agy-webchanel (agywc)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
DIST_DIR="${DIST_DIR:-dist}"
mkdir -p "$DIST_DIR"

echo "==> Generating THIRD_PARTY_LICENSES.txt via pip-licenses..."
"$PYTHON_BIN" -m piplicenses \
  --format=plain-vertical \
  --with-authors \
  --with-urls \
  --with-license-file \
  --no-license-path \
  --output-file="$DIST_DIR/THIRD_PARTY_LICENSES.txt"

echo "==> Compiling standalone onefile binary with Nuitka..."
"$PYTHON_BIN" -m nuitka \
  --standalone \
  --onefile \
  --assume-yes-for-downloads \
  --include-package=agy_webchanel \
  --include-package-data=googleapiclient \
  --include-package-data=google.auth \
  --output-dir="$DIST_DIR" \
  --output-filename=agywc \
  src/agy_webchanel/cli.py

cp LICENSE NOTICE "$DIST_DIR/"
echo "==> Build complete! Artifacts available in $DIST_DIR/"
