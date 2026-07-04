# -*- coding: utf-8 -*-
"""
diagnose_text_pipeline.py — прогон текста через весь текстовый пайплайн
XTTS Studio (normalizer -> chunker -> prosody -> word_replacer -> _split_by_language)
БЕЗ реального TTS-синтеза и БЕЗ записи новых слов в word_rules.json.

Используйте это ПЕРЕД тем, как гонять полноценную генерацию — особенно
для нетипичных/стресс-тестовых фраз (много аббревиатур подряд, смешанный
язык, необычная пунктуация). Так вы сразу видите, во что превратится текст,
и не рискуете "отравить" словарь произношений ошибочными auto-записями.

Запуск:
    python\\runtime\\python.exe diagnose_text_pipeline.py "Ваш тестовый текст"

Или без аргумента — возьмёт TEST_PHRASES ниже и прогонит все по очереди.
"""

import sys
import os

# Подключаем реальные модули проекта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "engine"))
sys.path.insert(0, os.path.dirname(__file__))

from engine.normalizer import TextNormalizer
from engine.chunker import TextChunker
from engine.word_replacer import WordReplacer
from engine.tts.utils import _split_by_language, detect_lang_adaptive

# Набор регрессионных фраз — держите здесь типичные проблемные случаи,
# накопленные за время работы над языковым переключением.
TEST_PHRASES = [
    ("Смешанный ru/en, короткие и длинные вставки",
     "Переключение контекста: We switch to English mode. The system continues "
     "processing without interruption. Voice synthesis must remain stable "
     "across language changes. Switching to technical mode: initialization "
     "complete. Loading modules... OK. Synchronization finished. "
     "Back to Russian mode. Проверка завершена успешно. Система работает "
     "стабильно. Финальная проверка: CPU GPU RAM JSON XML API GUI TTS XTTS "
     "AI ML LLM. End of stress test."),

    ("Одиночный технический термин в русском тексте",
     "Проверяем работу библиотеки soundfile в новом релизе."),

    ("Короткая английская вставка (<=3 слов)",
     "Это было действительно OK решение для проекта."),

    ("Длинная английская вставка (>3 слов)",
     "Он сказал: This is a really important update for everyone involved."),
]


def diagnose(text: str, word_rules_path: str):
    normalizer = TextNormalizer()
    chunker = TextChunker()
    word_replacer = WordReplacer(rules_path=word_rules_path)

    print("=" * 70)
    print("ИСХОДНЫЙ ТЕКСТ:")
    print(text)
    print()

    normalized = normalizer.normalize(text)
    normalized = normalizer.safe_character_filter(normalized)
    print("ПОСЛЕ normalize() + safe_character_filter():")
    print(normalized)
    print()

    chunks = chunker.chunk_text(normalized)
    print(f"ЧАНКОВ: {len(chunks)}")
    print()

    for i, chunk in enumerate(chunks):
        lang = detect_lang_adaptive(chunk)
        # persist_new=False — ВАЖНО: не пишем новые слова в словарь при диагностике!
        clean_chunk = word_replacer.apply(chunk, persist_new=False)
        subchunks = _split_by_language(clean_chunk, base_lang=lang)

        print(f"--- Chunk {i} (base_lang={lang}) ---")
        print(f"  до word_replacer: {chunk!r}")
        print(f"  после word_replacer: {clean_chunk!r}")
        print("  subchunks по языку:")
        for t, l in subchunks:
            marker = "🇬🇧" if l == "en" else "🇷🇺"
            print(f"    {marker} [{l}] {t}")
        print()


if __name__ == "__main__":
    # word_rules.json реального проекта — читаем как есть, но НЕ пишем в него
    # благодаря persist_new=False выше.
    word_rules_path = os.path.join(os.path.dirname(__file__), "word_rules.json")

    if len(sys.argv) > 1:
        custom_text = " ".join(sys.argv[1:])
        diagnose(custom_text, word_rules_path)
    else:
        for title, phrase in TEST_PHRASES:
            print(f"\n########## {title} ##########\n")
            diagnose(phrase, word_rules_path)