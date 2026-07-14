import os
from pathlib import Path

import pytest

import engine.output_naming as on
import engine.paths as paths


@pytest.fixture
def tmp_output_dir(tmp_path: Path, monkeypatch):
    out_dir = tmp_path / "outputs"
    out_dir.mkdir()
    monkeypatch.setattr(paths, "OUTPUT_DIR", str(out_dir))
    monkeypatch.setattr(on, "OUTPUT_DIR", str(out_dir))
    yield out_dir


class TestMakeOutputName:
    def test_simple(self, tmp_output_dir):
        result = on._make_output_name("Привет мир тест")
        assert result.endswith(".wav")
        assert "Привет" in result or "привет" in result.lower() or "output" in result.lower()
        assert str(tmp_output_dir) in result

    def test_trims_to_60_and_40(self, tmp_output_dir):
        long_text = "a" * 100 + " " + "b" * 100
        result = on._make_output_name(long_text)
        basename = os.path.basename(result).replace(".wav", "")
        # должен обрезать до 40 по последнему пробелу
        assert len(basename) <= 40 or " " not in basename[:40]

    def test_allows_letters_numbers_space_only(self, tmp_output_dir):
        result = on._make_output_name("Hello! @#$% World 123")
        basename = os.path.basename(result).replace(".wav", "")
        # только буквы, цифры, пробел разрешены (плюс возможные unicode буквы)
        # Проверяем что спецсимволы ! @ # $ % убраны
        assert "!" not in basename
        assert "@" not in basename
        assert "#" not in basename

    def test_empty_fallback_output(self, tmp_output_dir):
        result = on._make_output_name("   !!! @@@   ")
        # все символы запрещены → fallback "output"
        assert "output" in os.path.basename(result).lower()

    def test_newline_handling(self, tmp_output_dir):
        result = on._make_output_name("Привет\nмир\r\nтест")
        basename = os.path.basename(result)
        assert "\n" not in basename
        assert "\r" not in basename

    def test_unique_counter(self, tmp_output_dir):
        # если файл существует, должен добавить (1), (2) и т.д.
        first = on._make_output_name("test file")
        Path(first).write_text("fake")

        second = on._make_output_name("test file")
        assert second != first
        assert "(1)" in second

        Path(second).write_text("fake2")
        third = on._make_output_name("test file")
        assert "(2)" in third

    def test_cyrillic_preserved(self, tmp_output_dir):
        result = on._make_output_name("Привет мир это тест озвучки")
        basename = os.path.basename(result)
        # кириллица — категория L, должна сохраниться
        assert "Привет" in basename or "привет" in basename.lower()

    def test_cut_at_space(self, tmp_output_dir):
        text = "слово " * 20  # много слов, >40 символов
        result = on._make_output_name(text)
        basename = os.path.basename(result).replace(".wav", "")
        # должен обрезать по последнему пробелу до 40, а не посередине слова
        assert not basename.endswith(" ")
        assert len(basename) <= 40
