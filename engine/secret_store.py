"""Windows DPAPI-backed protection for credentials stored by XTTS Studio."""

import base64
import ctypes
import os
import sys
from ctypes import wintypes

PREFIX = "dpapi:v1:"
TEST_PREFIX = "test-only:v1:"


class SecretStoreUnavailable(RuntimeError):
    pass


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _blob(data: bytes):
    buffer = ctypes.create_string_buffer(data)
    return _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))), buffer


def _dpapi_protect(data: bytes) -> bytes:
    source, source_buffer = _blob(data)
    entropy, entropy_buffer = _blob(b"XTTS-Studio/API-credentials/v1")
    output = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if not crypt32.CryptProtectData(
        ctypes.byref(source), None, ctypes.byref(entropy), None, None, 0, ctypes.byref(output)
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        kernel32.LocalFree(output.pbData)
        del source_buffer, entropy_buffer


def _dpapi_unprotect(data: bytes) -> bytes:
    source, source_buffer = _blob(data)
    entropy, entropy_buffer = _blob(b"XTTS-Studio/API-credentials/v1")
    output = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if not crypt32.CryptUnprotectData(
        ctypes.byref(source), None, ctypes.byref(entropy), None, None, 0, ctypes.byref(output)
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        kernel32.LocalFree(output.pbData)
        del source_buffer, entropy_buffer


def _test_mode() -> bool:
    return os.environ.get("XTTS_TEST_SECRET_STORE") == "1"


def protect_secret(secret: str) -> str:
    value = str(secret or "")
    if not value:
        return ""
    raw = value.encode("utf-8")
    if sys.platform == "win32":
        return PREFIX + base64.b64encode(_dpapi_protect(raw)).decode("ascii")
    if _test_mode():
        return TEST_PREFIX + base64.b64encode(raw).decode("ascii")
    raise SecretStoreUnavailable("API credentials require Windows DPAPI")


def unprotect_secret(value: str) -> str:
    stored = str(value or "")
    if not stored:
        return ""
    try:
        if stored.startswith(PREFIX):
            if sys.platform != "win32":
                raise SecretStoreUnavailable(
                    "DPAPI credential can only be opened by its Windows user"
                )
            raw = base64.b64decode(stored[len(PREFIX) :], validate=True)
            return _dpapi_unprotect(raw).decode("utf-8")
        if stored.startswith(TEST_PREFIX) and _test_mode():
            return base64.b64decode(stored[len(TEST_PREFIX) :], validate=True).decode("utf-8")
    except SecretStoreUnavailable:
        raise
    except Exception as exc:
        raise SecretStoreUnavailable(f"credential decryption failed: {exc}") from exc
    # Legacy plaintext is returned only so the caller can immediately migrate it.
    return stored


def is_protected(value: str) -> bool:
    stored = str(value or "")
    return stored.startswith(PREFIX) or (_test_mode() and stored.startswith(TEST_PREFIX))
