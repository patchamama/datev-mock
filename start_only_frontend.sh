#!/usr/bin/env bash
#
# Frontend-only launcher (Linux/macOS)
#
# Serves just the standalone admin frontend (frontend/admin.html) over a
# plain local HTTP server, with NO mock backend involved -- point its own
# "Backend target & DATEV connection settings" card at whatever
# DATEV-compatible target you actually want (this project's FastAPI or Java
# mock, a real DATEV Desktop API, or someone else's compatible mock) once
# it's open. See the README FAQ ("Can I use just the frontend, with no
# backend running at all?").
#
# Uses Python's built-in `http.server` module (no third-party dependency)
# rather than opening frontend/admin.html directly via file:// -- a real
# http:// origin avoids that scheme's stricter, browser-dependent
# cross-origin request handling. Unlike start.sh's own zero-prerequisites
# portable-Python bootstrap, this script assumes a Python already on PATH --
# reasonable for a narrow, single-purpose convenience script that (unlike
# the full mock) doesn't need any third-party packages, only the standard
# library.

set -e

cd "$(dirname "${BASH_SOURCE[0]:-$0}")"

PORT="${DATEV_MOCK_FRONTEND_PORT:-8000}"

while [ $# -gt 0 ]; do
    case "$1" in
        --port)
            PORT="$2"
            shift 2
            ;;
        *)
            echo "ERROR: Unknown argument \"$1\""
            echo "Usage: $0 [--port PORT]"
            echo "       (or set the DATEV_MOCK_FRONTEND_PORT environment variable)"
            exit 1
            ;;
    esac
done

PYTHON_EXE=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON_EXE="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_EXE="python"
fi

if [ -z "$PYTHON_EXE" ]; then
    echo "ERROR: No Python found on PATH."
    echo "       This script only serves one static file locally and"
    echo "       deliberately doesn't bootstrap a portable Python for that"
    echo "       (see start.sh if you want the full mock's zero-prerequisites"
    echo "       installer instead). Install Python 3, or just open"
    echo "       frontend/admin.html directly in your browser via file://."
    exit 1
fi

echo "Starting the standalone frontend on http://127.0.0.1:$PORT/admin.html ..."
echo "(serving frontend/ only -- no mock backend is running; configure a"
echo " target in the page's own \"Backend target\" card once it opens.)"
echo ""

(
    sleep 1
    URL="http://127.0.0.1:$PORT/admin.html"
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$URL" >/dev/null 2>&1 || true
    elif command -v open >/dev/null 2>&1; then
        open "$URL" >/dev/null 2>&1 || true
    fi
) &

exec "$PYTHON_EXE" -m http.server "$PORT" --directory frontend
