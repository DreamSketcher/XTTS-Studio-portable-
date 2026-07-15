"""Ed25519 verification for immutable XTTS Studio update manifests."""

import base64

# Release verification key. The matching private key must never be committed or
# placed in a portable build. Rotate only through a separately authenticated
# application release.
UPDATE_MANIFEST_PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAgQpSKuteEEMxT8VNCTGZtlwkZttf8bu+BxsBjyJFaiA=
-----END PUBLIC KEY-----
"""


class ManifestSignatureError(RuntimeError):
    pass


def verify_manifest_signature(manifest_bytes: bytes, signature_bytes: bytes) -> None:
    """Raise ManifestSignatureError unless signature is valid for exact bytes."""
    if not manifest_bytes or not signature_bytes:
        raise ManifestSignatureError("манифест или подпись пусты")
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        key = serialization.load_pem_public_key(UPDATE_MANIFEST_PUBLIC_KEY_PEM)
        if not isinstance(key, Ed25519PublicKey):
            raise TypeError("ожидался Ed25519 public key")
        signature = base64.b64decode(signature_bytes.strip(), validate=True)
        key.verify(signature, manifest_bytes)
    except ManifestSignatureError:
        raise
    except Exception as exc:
        raise ManifestSignatureError(f"подпись update-манифеста недействительна: {exc}") from exc
