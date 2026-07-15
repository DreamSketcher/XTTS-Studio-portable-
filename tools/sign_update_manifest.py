"""Sign version.json with an offline Ed25519 private key."""

import argparse
import base64
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("version.json"))
    parser.add_argument("--signature", type=Path, default=Path("version.json.sig"))
    parser.add_argument("--private-key", type=Path, default=None)
    args = parser.parse_args()

    key_path = args.private_key or (
        Path(os.environ["XTTS_UPDATE_SIGNING_KEY"])
        if os.environ.get("XTTS_UPDATE_SIGNING_KEY")
        else None
    )
    if key_path is None:
        parser.error("pass --private-key or set XTTS_UPDATE_SIGNING_KEY")

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("update signing key must be Ed25519")
    from engine.update_signing import canonical_manifest_bytes

    signature = key.sign(canonical_manifest_bytes(args.manifest.read_bytes()))
    args.signature.write_bytes(base64.b64encode(signature) + b"\n")
    print(f"Signed {args.manifest} -> {args.signature}")


if __name__ == "__main__":
    main()
