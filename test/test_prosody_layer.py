import pytest

from engine.prosody_layer import ProsodyConfig, ProsodyLayer, create_prosody_layer


@pytest.fixture
def layer():
    return ProsodyLayer(ProsodyConfig(mode="balanced", intensity=1.0, breath_length="medium"))


class TestProsodyConfig:
    def test_factory(self):
        l = create_prosody_layer(mode="balanced", intensity=1.0, breath_length="medium")
        assert isinstance(l, ProsodyLayer)
        assert l.cfg.mode == "balanced"
        assert l.cfg.intensity == 1.0


class TestProcessBasics:
    def test_intensity_zero_returns_unchanged(self, layer):
        layer.cfg.intensity = 0.0
        text = "Привет. Но это тест."
        assert layer.process(text) == text

    def test_non_ru_en_returns_unchanged(self, layer):
        text = "Привет. Но это тест."
        assert layer.process(text, lang="fr") == text
        assert layer.process(text, lang="auto") == text

    def test_normalize(self, layer):
        assert layer._normalize("Привет  ,  мир !") == "Привет, мир!"
        assert layer._normalize("  много   пробелов  ") == "много пробелов"

    def test_cleanup(self, layer):
        # убирает ". ... ." → "... "
        cleaned = layer._cleanup("Привет. ... . Как дела")
        assert "..." in cleaned
        assert ". ... ." not in cleaned

        cleaned2 = layer._cleanup("Тест... ... ... Повтор")
        assert cleaned2.count("...") == 1 or "..." in cleaned2


class TestGetPause:
    def test_low_intensity(self, layer):
        layer.cfg.intensity = 0.5
        # base long → medium
        assert layer._get_pause("conclusion") == layer.PAUSE_MEDIUM
        # base medium → short
        assert layer._get_pause("contrast") == layer.PAUSE_SHORT

    def test_high_intensity(self, layer):
        layer.cfg.intensity = 1.5
        assert layer._get_pause("example") == layer.PAUSE_MEDIUM  # short → medium
        assert layer._get_pause("contrast") == layer.PAUSE_LONG  # medium → long

    def test_normal_intensity(self, layer):
        layer.cfg.intensity = 1.0
        assert layer._get_pause("contrast") == layer.PAUSE_MEDIUM
        assert layer._get_pause("conclusion") == layer.PAUSE_LONG
        assert layer._get_pause("example") == layer.PAUSE_SHORT


class TestInsertPauses:
    def test_contrast(self, layer):
        text = "Привет. Но это важно."
        result = layer._insert_contrast_pauses(text)
        # должен вставить паузу между "." и "Но"
        assert ", " in result or "..." in result
        assert "Но" in result

    def test_conclusion(self, layer):
        text = "Задача решена. Поэтому идём дальше."
        result = layer._insert_conclusion_pauses(text)
        assert "Поэтому" in result
        # пауза должна быть перед "Поэтому"
        assert "..." in result or "," in result

    def test_emphasis(self, layer):
        text = "Сделали работу. Важно отметить детали."
        result = layer._insert_emphasis_pauses(text)
        assert "Важно" in result

    def test_example(self, layer):
        text = "Есть варианты. Например, первый и второй."
        result = layer._insert_example_pauses(text)
        assert "Например" in result

    def test_case_insensitive(self, layer):
        text = "Привет. НО это тест."
        result = layer._insert_contrast_pauses(text)
        assert "НО" in result


class TestListProsody:
    def test_last_adds_dot(self, layer):
        assert layer._apply_list_prosody("первый пункт", is_last=True) == "первый пункт."
        assert layer._apply_list_prosody("последний.", is_last=True) == "последний."
        assert layer._apply_list_prosody("последний!", is_last=True) == "последний!"

    def test_middle_adds_comma(self, layer):
        assert layer._apply_list_prosody("промежуточный", is_last=False) == "промежуточный,"
        # если уже точка — заменяет на запятую
        assert layer._apply_list_prosody("пункт.", is_last=False) == "пункт,"
        # если уже запятая — остаётся
        assert layer._apply_list_prosody("пункт,", is_last=False) == "пункт,"

    def test_process_chunks_with_list(self, layer):
        chunks = [
            "1. первый пункт",
            "2. второй пункт",
            "Обычный текст не из списка.",
            "3. снова пункт",
            "4. последний пункт серии",
        ]
        # is_list_item для "1. " etc вернёт True по нашему stub
        result = layer.process_chunks(chunks, lang="ru")
        assert len(result) == len(chunks)
        # первый в серии не последний → запятая
        assert result[0].endswith(",")
        # второй в серии последний в своей серии (до обычного текста) → точка
        assert result[1].endswith(".")
        # обычный текст — без list обработки (может получить паузы, но не list comma)
        # третий — обычный
        # четвёртый — начало новой серии, не последний → запятая
        assert result[3].endswith(",")
        # пятый — последний → точка
        assert result[4].endswith(".")

    def test_process_chunks_all_list(self, layer):
        chunks = ["- яблоко", "- груша", "- слива"]
        result = layer.process_chunks(chunks, lang="ru")
        assert result[0].endswith(",")
        assert result[1].endswith(",")
        assert result[2].endswith(".")

    def test_process_full(self, layer):
        text = "Привет. Но это важно. Поэтому продолжаем."
        result = layer.process(text, lang="ru")
        assert isinstance(result, str)
        assert len(result) > 0
