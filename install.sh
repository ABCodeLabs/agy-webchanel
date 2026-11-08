#!/usr/bin/env bash
# One-liner installer for agy-webchanel (agywc)
# Usage: curl -fsSL https://raw.githubusercontent.com/ABCodeLabs/agy-webchanel/main/install.sh | bash
set -euo pipefail

REPO="ABCodeLabs/agy-webchanel"
REPO_GIT_URL="https://github.com/${REPO}.git"
BIN_NAME="agywc"

OS_RAW="$(uname -s)"
ARCH_RAW="$(uname -m)"

case "$OS_RAW" in
  Linux*)  OS="linux" ;;
  Darwin*) OS="macos" ;;
  *)       OS="unknown" ;;
esac

case "$ARCH_RAW" in
  x86_64|amd64)  ARCH="x86_64" ;;
  arm64|aarch64) ARCH="arm64" ;;
  *)             ARCH="unknown" ;;
esac

ASSET_NAME="agywc-${OS}-${ARCH}.tar.gz"

if [ "$(id -u)" -eq 0 ]; then
  INSTALL_DIR="${INSTALL_DIR:-/usr/local/bin}"
  SHARE_DIR="${SHARE_DIR:-/usr/local/share/agy-webchanel}"
else
  INSTALL_DIR="${INSTALL_DIR:-$HOME/.local/bin}"
  SHARE_DIR="${SHARE_DIR:-$HOME/.local/share/agy-webchanel}"
fi

mkdir -p "$INSTALL_DIR"

install_from_release() {
  if [ "$OS" = "unknown" ] || [ "$ARCH" = "unknown" ]; then
    return 1
  fi
  echo "==> Checking latest GitHub Release of $REPO for $ASSET_NAME..."
  local release_json download_url
  release_json="$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" 2>/dev/null || true)"
  if [ -z "$release_json" ]; then
    return 1
  fi

  download_url="$(printf '%s' "$release_json" | grep -Eo "https://github.com/${REPO}/releases/download/[^\"]+/${ASSET_NAME}" | head -n 1 || true)"
  if [ -z "$download_url" ]; then
    return 1
  fi

  local tmp_dir
  tmp_dir="$(mktemp -d)"
  echo "==> Downloading standalone binary from $download_url..."
  if ! curl -fsSL "$download_url" -o "$tmp_dir/$ASSET_NAME"; then
    rm -rf "$tmp_dir"
    return 1
  fi

  echo "==> Extracting archive..."
  tar -xzf "$tmp_dir/$ASSET_NAME" -C "$tmp_dir"
  install -m 0755 "$tmp_dir/$BIN_NAME" "$INSTALL_DIR/$BIN_NAME"
  ln -sf "$INSTALL_DIR/$BIN_NAME" "$INSTALL_DIR/agy-webchanel"
  rm -rf "$tmp_dir"
  return 0
}

install_from_source_venv() {
  echo "==> Installing agy-webchanel via isolated Python environment ($SHARE_DIR/venv)..."
  if ! command -v python3 >/dev/null 2>&1; then
    if command -v apt-get >/dev/null 2>&1; then
      echo "==> Installing python3 and python3-venv via apt-get..."
      if [ "$(id -u)" -eq 0 ]; then
        apt-get update -y && apt-get install -y python3 python3-venv python3-pip git
      elif command -v sudo >/dev/null 2>&1; then
        sudo apt-get update -y && sudo apt-get install -y python3 python3-venv python3-pip git
      fi
    fi
  fi

  mkdir -p "$SHARE_DIR"
  python3 -m venv "$SHARE_DIR/venv"
  "$SHARE_DIR/venv/bin/pip" install --upgrade pip >/dev/null
  "$SHARE_DIR/venv/bin/pip" install --upgrade "git+${REPO_GIT_URL}"
  ln -sf "$SHARE_DIR/venv/bin/agywc" "$INSTALL_DIR/agywc"
  ln -sf "$SHARE_DIR/venv/bin/agy-webchanel" "$INSTALL_DIR/agy-webchanel"
}

if install_from_release; then
  echo "✓ Standalone binary '$BIN_NAME' installed to $INSTALL_DIR/$BIN_NAME"
else
  echo "==> Prebuilt binary not found for ${OS}-${ARCH}; using automatic Python venv fallback..."
  install_from_source_venv
  echo "✓ '$BIN_NAME' installed to $INSTALL_DIR/$BIN_NAME"
fi

if ! echo ":$PATH:" | grep -q ":$INSTALL_DIR:"; then
  echo ""
  echo "Note: Ensure '$INSTALL_DIR' is in your PATH:"
  echo "  export PATH=\"$INSTALL_DIR:\$PATH\""
fi
