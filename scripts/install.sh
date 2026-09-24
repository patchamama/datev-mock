#!/usr/bin/env bash
#
# DATEV-Mock one-line installer (Linux/macOS)
#
# Downloads (or updates) the DATEV-Mock repository into a local folder and
# hands off to its own start.sh, which bootstraps Python (system Python if
# available, otherwise a portable download -- no system-wide install, no
# root required), installs dependencies, and launches the mock server.
#
# Usage (run from any directory):
#   curl -fsSL https://raw.githubusercontent.com/patchamama/datev-mock/main/scripts/install.sh | bash
#
# Set DATEV_MOCK_DIR to change where the repo is placed (default: ./datev-mock).

set -e

REPO_URL="https://github.com/patchamama/datev-mock.git"
REPO_ARCHIVE_URL="https://github.com/patchamama/datev-mock/archive/refs/heads/main.tar.gz"
TARGET_DIR="${DATEV_MOCK_DIR:-datev-mock}"

if [ -d "$TARGET_DIR/.git" ]; then
    echo "[1/2] $TARGET_DIR already exists, updating..."
    git -C "$TARGET_DIR" pull --ff-only
elif command -v git >/dev/null 2>&1; then
    echo "[1/2] Cloning DATEV-Mock into $TARGET_DIR ..."
    git clone --depth 1 "$REPO_URL" "$TARGET_DIR"
else
    echo "[1/2] git not found, downloading a source archive instead..."
    if [ -e "$TARGET_DIR" ]; then
        echo "ERROR: $TARGET_DIR already exists but is not a git repository."
        echo "       Remove it, or set DATEV_MOCK_DIR to a different path, and retry."
        exit 1
    fi
    if ! command -v curl >/dev/null 2>&1; then
        echo "ERROR: neither git nor curl was found. Please install one of them and retry."
        exit 1
    fi
    mkdir -p "$TARGET_DIR"
    curl -fsSL "$REPO_ARCHIVE_URL" | tar -xz -C "$TARGET_DIR" --strip-components=1
fi

cd "$TARGET_DIR"
chmod +x start.sh 2>/dev/null || true

echo "[2/2] Handing off to start.sh (installs Python dependencies and launches the mock)..."
exec ./start.sh
