#!/usr/bin/env bash
# One-liner installer for agy-webchanel (agywc)
# Usage: curl -fsSL https://raw.githubusercontent.com/ABCodeLabs/agy-webchanel/main/install.sh | bash
set -euo pipefail

REPO="ABCodeLabs/agy-webchanel"
BIN_NAME="agywc"

OS_RAW="$(uname -s)"
ARCH_RAW="$(uname -m)"

case "$OS_RAW" in
  Linux*)
    OS="linux"
    ;;
  Darwin*)
    OS="macos"
    ;;
  *)
    echo "Error: Unsupported operating system '$OS_RAW'. For Windows, download the .zip from GitHub Releases." >&2
    exit 1
    ;;
esac

case "$ARCH_RAW" in
  x86_64|amd64)
    ARCH="x86_64"
    ;;
  arm64|aarch64)
    ARCH="arm64"
    ;;
  *)
    echo "Error: Unsupported architecture '$ARCH_RAW'." >&2
    exit 1
    ;;
esac

ASSET_NAME="agywc-${OS}-${ARCH}.tar.gz"

if [ "$(id -u)" -eq 0 ]; then
  INSTALL_DIR="${INSTALL_DIR:-/usr/local/bin}"
else
  INSTALL_DIR="${INSTALL_DIR:-$HOME/.local/bin}"
fi

mkdir -p "$INSTALL_DIR"

echo "==> Checking latest release of $REPO for $ASSET_NAME..."
RELEASE_JSON="$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest")"
DOWNLOAD_URL="$(printf '%s' "$RELEASE_JSON" | grep -Eo "https://github.com/${REPO}/releases/download/[^\"]+/${ASSET_NAME}" | head -n 1 || true)"

if [ -z "$DOWNLOAD_URL" ]; then
  echo "Error: Could not find asset '$ASSET_NAME' in the latest release of $REPO." >&2
  exit 1
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "==> Downloading $DOWNLOAD_URL..."
curl -fsSL "$DOWNLOAD_URL" -o "$TMP_DIR/$ASSET_NAME"

echo "==> Extracting archive..."
tar -xzf "$TMP_DIR/$ASSET_NAME" -C "$TMP_DIR"

install -m 0755 "$TMP_DIR/$BIN_NAME" "$INSTALL_DIR/$BIN_NAME"
ln -sf "$INSTALL_DIR/$BIN_NAME" "$INSTALL_DIR/agy-webchanel"

echo "✓ Installed '$BIN_NAME' (and alias 'agy-webchanel') to $INSTALL_DIR"
if ! echo ":$PATH:" | grep -q ":$INSTALL_DIR:"; then
  echo "Note: Ensure '$INSTALL_DIR' is in your PATH:"
  echo "  export PATH=\"$INSTALL_DIR:\$PATH\""
fi
