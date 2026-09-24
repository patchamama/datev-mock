#!/usr/bin/env bash
#
# DATEV-Mock launcher (Linux/macOS)
#
# Works with zero prerequisites: if a usable system python3 (>= 3.9) is
# found on PATH, it is used via a project-local .venv. Otherwise this
# script downloads a portable, project-local Python (an
# astral-sh/python-build-standalone "install_only" build) into
# python-portable/ and uses that instead. Nothing is installed
# system-wide and no root/admin rights are required.

set -e

cd "$(dirname "${BASH_SOURCE[0]:-$0}")"

PYTHON_EXE=""
PORT=58452

version_ge_39() {
    # $1 is a version string like "3.11.4"
    local major minor
    major="$(echo "$1" | cut -d. -f1)"
    minor="$(echo "$1" | cut -d. -f2)"
    if [ -z "$major" ] || [ -z "$minor" ]; then
        return 1
    fi
    if [ "$major" -gt 3 ]; then
        return 0
    fi
    if [ "$major" -eq 3 ] && [ "$minor" -ge 9 ]; then
        return 0
    fi
    return 1
}

echo "[1/5] Checking for a usable system python3 (>= 3.9)..."

SYSTEM_PYTHON_OK=0
if command -v python3 >/dev/null 2>&1; then
    SYS_VERSION="$(python3 --version 2>&1 | awk '{print $2}')"
    if version_ge_39 "$SYS_VERSION"; then
        echo "      Found system Python: python3 ($SYS_VERSION)"
        SYSTEM_PYTHON_OK=1
    else
        echo "      System python3 found but too old ($SYS_VERSION), need >= 3.9."
    fi
else
    echo "      No python3 found on PATH."
fi

if [ "$SYSTEM_PYTHON_OK" -eq 1 ]; then
    if [ ! -d ".venv" ]; then
        echo "[2/5] Creating virtual environment in .venv ..."
        python3 -m venv .venv
    else
        echo "[2/5] Virtual environment .venv already exists."
    fi

    echo "[3/5] Installing dependencies into .venv ..."
    # shellcheck disable=SC1091
    . .venv/bin/activate
    pip install --quiet --upgrade pip
    pip install --quiet -r requirements.txt

    PYTHON_EXE="$(pwd)/.venv/bin/python"
else
    echo "[2/5] Bootstrapping a portable, project-local Python (no system install) ..."

    if [ -x "python-portable/bin/python3" ]; then
        echo "      Reusing previously bootstrapped portable Python in python-portable/ ..."
        PYTHON_EXE="$(pwd)/python-portable/bin/python3"
    else
        if ! command -v curl >/dev/null 2>&1; then
            echo "ERROR: curl is required to bootstrap a portable Python but was not found."
            echo "       Please install python3 yourself (e.g. 'apt install python3 python3-venv'"
            echo "       or 'brew install python3') and re-run this script."
            exit 1
        fi

        OS_NAME="$(uname -s)"
        ARCH_NAME="$(uname -m)"

        case "$OS_NAME" in
            Linux)
                case "$ARCH_NAME" in
                    x86_64) TARGET_TRIPLE="x86_64-unknown-linux-gnu" ;;
                    aarch64|arm64) TARGET_TRIPLE="aarch64-unknown-linux-gnu" ;;
                    *) TARGET_TRIPLE="" ;;
                esac
                ;;
            Darwin)
                case "$ARCH_NAME" in
                    x86_64) TARGET_TRIPLE="x86_64-apple-darwin" ;;
                    arm64) TARGET_TRIPLE="aarch64-apple-darwin" ;;
                    *) TARGET_TRIPLE="" ;;
                esac
                ;;
            *)
                TARGET_TRIPLE=""
                ;;
        esac

        if [ -z "$TARGET_TRIPLE" ]; then
            echo "ERROR: Could not determine a supported platform for automatic portable"
            echo "       Python download (OS='$OS_NAME', arch='$ARCH_NAME')."
            echo "       Please install python3 yourself (e.g. 'apt install python3 python3-venv'"
            echo "       or 'brew install python3') and re-run this script."
            exit 1
        fi

        echo "      Detected platform: $TARGET_TRIPLE"
        echo "      Looking up the latest python-build-standalone release ..."

        RELEASE_JSON="$(curl -fsSL https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest || true)"
        if [ -z "$RELEASE_JSON" ]; then
            echo "ERROR: Failed to query the GitHub releases API for python-build-standalone."
            echo "       Please install python3 yourself and re-run this script."
            exit 1
        fi

        ASSET_URL="$(echo "$RELEASE_JSON" \
            | grep -o '"browser_download_url": *"[^"]*cpython-3\.12[^"]*"' \
            | grep "$TARGET_TRIPLE" \
            | grep -- "-install_only.tar.gz\"" \
            | head -n1 \
            | sed -E 's/.*"(https:[^"]+)"/\1/')"

        if [ -z "$ASSET_URL" ]; then
            echo "ERROR: Could not find a matching cpython-3.12 install_only build for"
            echo "       $TARGET_TRIPLE in the latest python-build-standalone release."
            echo "       Please install python3 yourself (e.g. 'apt install python3 python3-venv'"
            echo "       or 'brew install python3') and re-run this script."
            exit 1
        fi

        echo "      Downloading $ASSET_URL ..."
        TMP_TARBALL="$(mktemp -t datev-mock-python-XXXXXX.tar.gz)"
        if ! curl -fsSL "$ASSET_URL" -o "$TMP_TARBALL"; then
            echo "ERROR: Failed to download the portable Python build."
            rm -f "$TMP_TARBALL"
            exit 1
        fi

        echo "      Extracting portable Python into python-portable/ ..."
        rm -rf python-portable
        mkdir -p python-portable
        if ! tar -xzf "$TMP_TARBALL" -C python-portable; then
            echo "ERROR: Failed to extract the portable Python build."
            rm -f "$TMP_TARBALL"
            exit 1
        fi
        rm -f "$TMP_TARBALL"

        # python-build-standalone "install_only" tarballs extract to a
        # top-level python/ directory (python/bin/python3, python/lib, ...).
        # Flatten it so the final binary lands at a predictable path.
        if [ -d "python-portable/python" ]; then
            for entry in python-portable/python/*; do
                mv "$entry" "python-portable/$(basename "$entry")"
            done
            rmdir python-portable/python
        fi

        if [ ! -x "python-portable/bin/python3" ]; then
            echo "ERROR: Portable Python extraction did not produce python-portable/bin/python3."
            echo "       Please install python3 yourself and re-run this script."
            exit 1
        fi

        PYTHON_EXE="$(pwd)/python-portable/bin/python3"
    fi

    echo "[3/5] Installing dependencies into the portable Python ..."
    "$PYTHON_EXE" -m pip install --quiet -r requirements.txt
fi

if [ -f "certs/cert.pem" ] && [ -f "certs/key.pem" ]; then
    echo "[4/5] TLS certificate already present in certs/."
else
    echo "[4/5] Generating a self-signed TLS certificate for 127.0.0.1 ..."
    "$PYTHON_EXE" certs/generate_cert.py
fi

echo "[5/5] Starting the DATEV mock server on https://127.0.0.1:$PORT ..."

# Auto-open the default browser at /admin a couple seconds after uvicorn
# launches, in parallel — uvicorn needs a moment to actually bind the port.
# Backgrounded and non-fatal: never blocks or fails server startup, and
# falls back to a plain message in headless environments with neither
# xdg-open (Linux) nor open (macOS) available.
(
    sleep 2
    ADMIN_URL="https://127.0.0.1:$PORT/admin"
    xdg-open "$ADMIN_URL" >/dev/null 2>&1 || open "$ADMIN_URL" >/dev/null 2>&1 || echo "Open $ADMIN_URL in your browser."
) &

# --no-access-log: app/request_log.py's middleware already logs every
# request in clean plain text; uvicorn's own colored access log was
# printing a redundant second line per request, with raw ANSI escape
# codes on terminals that don't render them.
exec "$PYTHON_EXE" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" \
    --ssl-keyfile certs/key.pem --ssl-certfile certs/cert.pem --no-access-log
