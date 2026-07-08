"""
test/test_sha256_verification.py

Проверяет, что механизм SHA256 в engine/updater.py реально работает:
  1. Правильный хэш -> файл проходит проверку и остаётся в staging.
  2. Неправильный хэш -> файл отклоняется и удаляется.
  3. Хэш отсутствует в манифесте (None) -> файл отклоняется (это та дыра,
     которая раньше тихо пропускала проверку — теперь должна блокировать).

Работает БЕЗ сети: подменяет сетевую загрузку локальными тестовыми
данными, чтобы не трогать GitHub и не зависеть от реального релиза.

Запуск (из корня проекта):
    python\\runtime\\python.exe test\\test_sha256_verification.py
"""
import hashlib
import io
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from engine import updater  # noqa: E402

FAKE_CONTENT = b"XTTS Studio SHA256 self-test payload - do not modify"
CORRECT_HASH = hashlib.sha256(FAKE_CONTENT).hexdigest()
WRONG_HASH = "0" * 64
TEST_RELATIVE_PATH = "test/_sha256_selftest.tmp"


def _fake_urlopen(url, timeout=15, max_retries=None):
    """Заменяет реальный сетевой запрос локальными тестовыми байтами."""
    return io.BytesIO(FAKE_CONTENT)


def _staged_path() -> str:
    return os.path.join(updater.STAGING_DIR, TEST_RELATIVE_PATH.replace("/", os.sep))


def _cleanup():
    for p in (_staged_path(), _staged_path() + ".part"):
        if os.path.exists(p):
            os.remove(p)


def _check(name: str, ok: bool, expect_ok: bool) -> bool:
    file_exists = os.path.exists(_staged_path())
    success = (ok == expect_ok) and (file_exists == expect_ok)
    status = "PASS" if success else "FAIL"
    print(f"  [{status}] {name} (вернул={ok}, файл в staging={file_exists})")
    return success


def run() -> bool:
    results = []
    original_urlopen = updater._urlopen_with_retry
    updater._urlopen_with_retry = _fake_urlopen

    try:
        os.makedirs(updater.STAGING_DIR, exist_ok=True)

        print("[1/3] Правильный SHA256 — файл должен пройти проверку")
        _cleanup()
        ok = updater._download_to_staging(TEST_RELATIVE_PATH, CORRECT_HASH)
        results.append(_check("correct hash accepted", ok, expect_ok=True))
        _cleanup()

        print("[2/3] Неправильный SHA256 — файл должен быть отклонён")
        ok = updater._download_to_staging(TEST_RELATIVE_PATH, WRONG_HASH)
        results.append(_check("wrong hash rejected", ok, expect_ok=False))
        _cleanup()

        print("[3/3] Хэш отсутствует в манифесте (None) — файл должен быть отклонён")
        ok = updater._download_to_staging(TEST_RELATIVE_PATH, None)
        results.append(_check("missing hash rejected", ok, expect_ok=False))
        _cleanup()

    finally:
        updater._urlopen_with_retry = original_urlopen
        _cleanup()
        try:
            if os.path.isdir(updater.STAGING_DIR) and not os.listdir(updater.STAGING_DIR):
                os.rmdir(updater.STAGING_DIR)
        except OSError:
            pass

    passed = sum(results)
    total = len(results)
    print(f"\nИтого: {passed}/{total} passed")
    return passed == total


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)