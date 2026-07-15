from engine.gui.chat_window import chat_messages


def test_display_line_estimate_is_bounded_for_huge_text():
    text = ("word " * 200_000) + "\n" + ("x" * 500_000)
    assert chat_messages._estimate_display_lines(text, 80) == 80


def test_display_line_estimate_handles_short_and_empty_text():
    assert chat_messages._estimate_display_lines("", 80) == 1
    assert chat_messages._estimate_display_lines("hello", 80) == 1
    assert chat_messages._estimate_display_lines("a\nb", 80) == 2


def test_initial_and_page_limits_are_bounded():
    assert 1_000 <= chat_messages._CHAT_INITIAL_CHARS <= 16_000
    assert 1_000 <= chat_messages._CHAT_PAGE_CHARS <= 16_000


def test_text_measurement_samples_are_bounded():
    assert chat_messages._CHAT_MEASURE_MAX_LINES <= 50
    assert chat_messages._CHAT_MEASURE_MAX_CHARS_PER_LINE <= 1000
