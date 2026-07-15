import base64

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from engine import update_signing


def _temporary_keypair(monkeypatch):
    private = Ed25519PrivateKey.generate()
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    monkeypatch.setattr(update_signing, "UPDATE_MANIFEST_PUBLIC_KEY_PEM", public_pem)
    return private


def test_valid_signature(monkeypatch):
    private = _temporary_keypair(monkeypatch)
    manifest = b'{"version":"1.2.3"}'
    signature = base64.b64encode(private.sign(manifest))
    update_signing.verify_manifest_signature(manifest, signature)


def test_modified_manifest_is_rejected(monkeypatch):
    private = _temporary_keypair(monkeypatch)
    signature = base64.b64encode(private.sign(b"original"))
    with pytest.raises(update_signing.ManifestSignatureError):
        update_signing.verify_manifest_signature(b"modified", signature)


@pytest.mark.parametrize("signature", [b"", b"not-base64", base64.b64encode(b"short")])
def test_invalid_signature_is_rejected(monkeypatch, signature):
    _temporary_keypair(monkeypatch)
    with pytest.raises(update_signing.ManifestSignatureError):
        update_signing.verify_manifest_signature(b"manifest", signature)
