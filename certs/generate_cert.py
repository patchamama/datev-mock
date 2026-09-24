"""Generates a self-signed TLS cert+key for 127.0.0.1/localhost.

Used to serve the mock over HTTPS on port 58452, matching the real DATEV
Desktop API's transport. Not required by the test suite (FastAPI's
TestClient talks to the ASGI app in-process, no TLS involved) — this is for
manually running the server with uvicorn.

Usage:
    python certs/generate_cert.py
Writes `certs/cert.pem` and `certs/key.pem` under the runtime base dir (see
`app.runtime_paths.base_dir`): the project root from a source checkout, or
the folder containing the .exe when frozen.
"""
from __future__ import annotations

import datetime
import ipaddress
import sys
from pathlib import Path

# Allow `python certs/generate_cert.py` to find the `app` package (repo root
# isn't on sys.path when run as a script, only certs/ is).
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app.runtime_paths import base_dir

CERTS_DIR = base_dir() / "certs"
CERT_PATH = CERTS_DIR / "cert.pem"
KEY_PATH = CERTS_DIR / "key.pem"


def generate_self_signed_cert() -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "DATEV-Mock"),
        ]
    )

    now = datetime.datetime.now(datetime.timezone.utc)

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )

    CERTS_DIR.mkdir(parents=True, exist_ok=True)

    KEY_PATH.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    CERT_PATH.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    print(f"Wrote {CERT_PATH}")
    print(f"Wrote {KEY_PATH}")


if __name__ == "__main__":
    generate_self_signed_cert()
