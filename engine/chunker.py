import re

from engine.text_utils import is_list_item as _is_list_item
from engine.text_utils import has_inline_list as _has_inline_list


# =========================
# ENUMERATION HELPERS
# =========================
def _is_short_enum_sentence(text: str, max_len: int = 80, max_words: int = 10) -> bool:
    """Короткое предложение, пригодное для семантической группы."""
    t = (text or "").strip()
    if not t:
        return False
    if len(t) > max_len:
        return False
    if len(re.findall(r'\S+', t)) > max_words:
        return False
    return True


def _ends_with_colon(text: str) -> bool:
    """Заканчивается ли предложение двоеточием (с возможной завершающей пунктуацией/кавычкой)."""
    t = (text or "").rstrip(" \"')]}»”")
    return t.endswith(":")


class TextChunker:
    def __init__(self):
        self.max_chunk_size   = 180
        self.min_chunk_size   = 40
        self.list_merge_limit = 160
        # Лимит для семантической группы (перечисление, серия коротких фраз).
        # Может превышать max_chunk_size, но безопасно для XTTS inference.
        self.enum_group_limit = 200

    def chunk_text(self, text):
        sentences = self._split_into_sentences(text)

        # NEW: связываем перечисления и серии в логические блоки,
        # чтобы XTTS видел их как один интонационный контекст
        sentences = self._group_enumerations(sentences)

        raw_chunks = []
        for sentence in sentences:
            raw_chunks.extend(self._split_long_sentence(sentence))

        raw_chunks = self._merge_list_items(raw_chunks)
        merged = self._merge_short_chunks(raw_chunks)

        result = []
        for c in merged:
            c = c.strip()
            if c and c[-1] not in ".!?":
                c += "."
            result.append(c)
        return [c for c in result if c]

    # =========================
    # SENTENCE SPLITTING
    # =========================
    def _split_into_sentences(self, text: str) -> list:
        """
        Режет на предложения, защищая от ложных разрывов на:
        - многоточиях '...' (после нормализатора это бывшее тире,
          а также авторская пауза — НЕ граница предложения);
        - аббревиатурах из 2+ заглавных букв
          (XTTS, TTS, AI, API, GPU, ЦРУ, МГУ, СССР ...);
        - типичных сокращениях (т.е., т.к., т.д., и.о. ...).
        """
        # 1) защищаем многоточия (бывшие тире / авторская пауза)
        protected = text.replace("...", "<ELLIPSIS>")

        # 2) скрываем точки после ALL_CAPS аббревиатур (латиница и кириллица)
        protected = re.sub(
            r'\b([A-ZА-ЯЁ]{2,})\.',
            r'\1<DOT>',
            protected
        )

        # 3) скрываем точки в типичных русских/английских сокращениях
        #    т.е., т.к., т.д., и.о., а.к.а. и т.п.
        protected = re.sub(
            r'\b([а-яёa-z]{1,4})\.\s+(?=[а-яёa-z])',
            lambda m: m.group(0).replace('.', '<DOT>', 1),
            protected
        )

        # 4) режем по концам предложений
        sentences = re.split(r'(?<=[.!?])\s+', protected)

        # 5) восстанавливаем все замены
        sentences = [
            s.replace('<DOT>', '.').replace('<ELLIPSIS>', '...')
            for s in sentences
        ]
        return sentences

    # =========================
    # NEW: ENUMERATION GROUPING
    # =========================
    def _group_enumerations(self, sentences: list) -> list:
        """
        Склеивает связанные по смыслу короткие предложения в один блок,
        чтобы XTTS воспринимал их как единый интонационный контекст:

        ТРИГГЕР 1 — двоеточие:
            "...работает по принципу: Скачал. Распаковал. Запустил."
            После предложения с ':' собираем все короткие подряд идущие
            предложения, пока укладываемся в enum_group_limit.

        ТРИГГЕР 2 — серия коротких предложений:
            "Скачал. Распаковал. Запустил."
            Два и более коротких предложений подряд считаются перечислением.

        Длинные предложения (обычная проза) обрабатываются как раньше.
        """
        result = []
        n = len(sentences)
        i = 0

        while i < n:
            current = (sentences[i] or "").strip()
            if not current:
                i += 1
                continue

            after_colon = _ends_with_colon(current)
            next_text = (sentences[i + 1] or "").strip() if i + 1 < n else ""
            next_is_short = _is_short_enum_sentence(next_text)
            current_short = _is_short_enum_sentence(current)

            # триггер: ":" + короткое следующее ИЛИ серия коротких
            start_group = (after_colon and next_is_short) or \
                          (current_short and next_is_short)

            if start_group:
                group = [current]
                group_len = len(current)
                j = i + 1

                while j < n:
                    nxt = (sentences[j] or "").strip()
                    if not nxt:
                        j += 1
                        continue

                    # длинное предложение завершает группу
                    if not _is_short_enum_sentence(nxt):
                        break

                    new_len = group_len + 1 + len(nxt)
                    if new_len > self.enum_group_limit:
                        break

                    group.append(nxt)
                    group_len = new_len
                    j += 1

                if len(group) >= 2:
                    result.append(" ".join(group))
                    i = j
                    continue

            result.append(current)
            i += 1

        return result

    # =========================
    # MERGE LIST ITEMS
    # =========================
    def _merge_list_items(self, chunks: list) -> list:
        result = []
        buffer = ""

        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk:
                continue

            is_item = _is_list_item(chunk)

            if is_item:
                candidate = (buffer + " " + chunk).strip() if buffer else chunk
                if len(candidate) <= self.list_merge_limit:
                    buffer = candidate
                else:
                    if buffer:
                        result.append(buffer)
                    buffer = chunk
            else:
                if buffer:
                    result.append(buffer)
                    buffer = ""
                result.append(chunk)

        if buffer:
            result.append(buffer)

        return result

    # =========================
    # SPLIT LONG SENTENCE
    # =========================
    def _split_long_sentence(self, sentence):
        if len(sentence) <= self.max_chunk_size:
            return [sentence]

        # Защита семантической группы: если внутри уже несколько
        # предложений (точки/!/?) и общий размер в пределах
        # enum_group_limit — НЕ режем, это перечисление.
        period_count = sentence.count('.') + sentence.count('!') + sentence.count('?')
        if period_count >= 2 and len(sentence) <= self.enum_group_limit:
            return [sentence]

        if _has_inline_list(sentence) and len(sentence) <= self.list_merge_limit:
            return [sentence]

        parts = re.split(r'[,;:]', sentence)
        result = []
        buffer = ""
        for part in parts:
            part = part.strip()
            if not part:
                continue
            candidate = (buffer + ", " + part).strip(", ")
            if len(candidate) <= self.max_chunk_size + 30:
                buffer = candidate
            else:
                if buffer and len(part) < 30:
                    buffer = candidate
                else:
                    if buffer:
                        result.append(buffer.strip())
                    buffer = part
        if buffer:
            result.append(buffer.strip())
        return result

    # =========================
    # MERGE SHORT CHUNKS
    # =========================
    def _merge_short_chunks(self, chunks):
        result = []
        buffer = ""

        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk:
                continue

            if len(buffer) < self.min_chunk_size:
                buffer = (buffer + " " + chunk).strip()
                continue

            if len(buffer) + len(chunk) + 1 <= self.max_chunk_size:
                buffer = (buffer + " " + chunk).strip()
            else:
                if buffer:
                    result.append(buffer)
                buffer = chunk

        if buffer:
            result.append(buffer)

        return result