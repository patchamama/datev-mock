"""PyInstaller entry point: runs the DATEV mock as a standalone executable.

Mirrors the final `uvicorn` invocation in `start.sh`/`start.bat` (same host,
port, and TLS cert args), but generates the self-signed cert in-process
(via a direct function call, not a subprocess) since a frozen .exe has no
separate Python interpreter available on the target machine.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make both `app` and `certs` importable regardless of whether this runs as
# a plain script (source checkout) or frozen by PyInstaller (sys._MEIPASS).
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import uvicorn

from app.main import app
from app.runtime_paths import base_dir
from certs.generate_cert import generate_self_signed_cert

HOST = "127.0.0.1"
PORT = 58452


def main() -> None:
    certs_dir = base_dir() / "certs"
    cert_path = certs_dir / "cert.pem"
    key_path = certs_dir / "key.pem"

    if not (cert_path.exists() and key_path.exists()):
        generate_self_signed_cert()

    # Pass the ASGI app object directly (not the "app.main:app" import
    # string) so PyInstaller's static analysis picks up `app.main` via the
    # normal `import` statement above -- a string target is resolved by
    # uvicorn at runtime via importlib, which a frozen build can't discover
    # ahead of time without extra --hidden-import bookkeeping.
    # access_log=False: app/request_log.py's middleware already logs every
    # request in clean plain text; uvicorn's own colored access log was
    # printing a redundant second line per request.
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        ssl_keyfile=str(key_path),
        ssl_certfile=str(cert_path),
        access_log=False,
    )


if __name__ == "__main__":
    main()
