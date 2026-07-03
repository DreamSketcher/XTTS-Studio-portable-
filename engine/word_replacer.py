import json
import os
import re
from typing import Optional


# =========================
# SEED DICTIONARY
# =========================
# Эти слова пишутся в word_rules.json ОДИН РАЗ при первом запуске —
# в категорию "builtin". После этого они живут только в JSON и
# редактируются/удаляются через окно "📖 Словарь" как любые другие.
# Код трогать больше не нужно — это просто стартовый набор данных.
_SEED_DICTIONARY = {
    "python":      "пайтон",
    "pytorch":     "пайторч",
    "tensorflow":  "тензорфлоу",
    "numpy":       "нампай",
    "pandas":      "пандас",
    "django":      "джанго",
    "flask":       "фласк",
    "node":        "ноуд",
    "nodejs":      "ноуд джей эс",
    "github":      "гитхаб",
    "gitlab":      "гитлаб",
    "google":      "гугл",
    "microsoft":   "майкрософт",
    "nvidia":      "энвидиа",
    "openai":      "оупен эй ай",
    "ubuntu":      "убунту",
    "docker":      "докер",
    "linux":       "линукс",
    "windows":     "виндоус",
    "android":     "андроид",
    "chrome":      "хром",
    "firefox":     "файрфокс",
    "chatgpt":     "чат джи пи ти",
    "claude":      "клод",
    "gemini":      "джемини",
    "coqui":       "кокуи",
    "xtts":        "икс ти ти эс",
    "speaker embedding": "спикер эмбеддинг",
    "top p":             "топ пи",
    "top k":             "топ кей",
    "cross correlation": "кросс корреляция",
    "drag and drop":     "драг энд дроп",
    "temperature":       "температура",
    "wav":               "вав",
    "ffmpeg":            "эфэфмпег",
    "bat":               "бат",
    "saas":              "саас",
}

# Приоритет категорий при сборке flat_rules: позже = выше приоритет.
# builtin — базовые сиды (низший приоритет)
# auto — слова, добавленные эвристическим автодетектором
# ai_corrected — исправления от AI Conductor
# custom — ручные правки пользователя через окно "📖 Словарь" (высший приоритет)
_CATEGORY_PRIORITY = ["builtin", "auto", "ai_corrected", "custom"]

_LATIN_LETTER_MAP = {
    "a": "эй",  "b": "би",  "c": "си",  "d": "ди",  "e": "и",   "f": "эф",
    "g": "джи", "h": "эйч", "i": "ай",  "j": "джей","k": "кей", "l": "эл",
    "m": "эм",  "n": "эн",  "o": "оу",  "p": "пи",  "q": "кью", "r": "ар",
    "s": "эс",  "t": "ти",  "u": "ю",   "v": "ви",  "w": "дабл ю",
    "x": "икс", "y": "уай", "z": "зед",
}

_SERVICE_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "and", "or", "but", "if", "of", "in", "on", "at", "to", "for", "with",
    "as", "by", "from", "this", "that", "it", "its", "his", "her", "their",
    "not", "no", "yes", "ok", "okay", "vs", "etc", "id",
    "fast", "slow", "speed", "high", "low", "new", "old", "good", "bad",
    "we", "you", "he", "she", "they", "them", "our", "your", "my",
    "end", "back", "up", "down", "out", "off", "on", "now", "then",
    "can", "will", "must", "may", "has", "had", "do", "did", "does",
}

_DIGRAPHS = [
    ("tion", "шн"), ("sion", "жн"),
    ("ough", "оу"), ("augh", "аф"),
    ("th", "т"), ("sh", "ш"), ("ch", "ч"), ("ph", "ф"), ("wh", "у"),
    ("ck", "к"), ("ng", "нг"), ("qu", "кв"),
    ("ee", "и"), ("oo", "у"), ("ou", "ау"), ("ow", "оу"),
    ("au", "ау"),
    ("ai", "эй"), ("ay", "эй"), ("ea", "и"), ("ie", "ай"),
    ("oa", "оу"), ("ue", "ю"), ("ui", "ю"),
]

_SINGLE_SOUND = {
    "a": "а", "b": "б", "c": "к", "d": "д", "e": "е", "f": "ф",
    "g": "г", "h": "х", "i": "и", "j": "дж", "k": "к", "l": "л",
    "m": "м", "n": "н", "o": "о", "p": "п", "q": "к", "r": "р",
    "s": "с", "t": "т", "u": "а", "v": "в", "w": "в", "x": "кс",
    "y": "и", "z": "з",
}

_VOWELS = set("aeiou")

_NUM_WORDS = {
    "0": "ноль", "1": "один", "2": "два", "3": "три", "4": "четыре",
    "5": "пять", "6": "шесть", "7": "семь", "8": "восемь", "9": "девять",
}


def _looks_like_abbrev(word: str) -> bool:
    """Капс-аббревиатура (XTTS, CPU, GPU) -> читаем побуквенно."""
    if not word or len(word) < 2 or len(word) > 6:
        return False
    if not word.isalpha():
        return False
    if not word.isascii():
        return False
    if not word.isupper():
        return False
    return True


def _auto_transliterate_abbrev(word: str) -> str:
    parts = []
    for ch in word.lower():
        parts.append(_LATIN_LETTER_MAP.get(ch, ch))
    return " ".join(parts)


def _looks_like_lowercase_term(word: str) -> bool:
    """
    Lowercase-слово, не входящее в список служебных слов -> кандидат на
    слоговую транслитерацию (pydub, tkinter, soundfile, ffmpeg,
    tkinterdnd2, num2words).
    """
    if not word or len(word) < 2:
        return False
    if not word.isascii():
        return False
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9]*', word):
        return False
    if word.isupper():
        return False
    if word.lower() in _SERVICE_WORDS:
        return False
    return True


def _transliterate_term_word(word: str) -> str:
    """
    Транслитерация технического термина (эвристика, не словарь).
    Используется только как запасной вариант для слов, которых ЕЩЁ НЕТ
    в word_rules.json — после первого срабатывания слово автоматически
    сохраняется в категорию "auto" и больше не идёт через эвристику.
    Если результат неверный — поправьте слово в окне "📖 Словарь",
    оно перейдёт в "custom" и будет иметь приоритет навсегда.
    """
    segments = re.findall(r'[a-zA-Z]+|\d+', word)
    parts = []
    for seg in segments:
        if seg.isdigit():
            parts.append(" ".join(_NUM_WORDS.get(d, d) for d in seg))
        elif len(seg) <= 3:
            parts.append(" ".join(_LATIN_LETTER_MAP.get(c, c) for c in seg.lower()))
        else:
            parts.append(_letters_to_word_sound(seg))
    return " ".join(p for p in parts if p)


def _letters_to_word_sound(letters: str) -> str:
    w = letters.lower()
    out = []
    i = 0
    n = len(w)
    while i < n:
        if w[i] == "y" and (i == 0 or w[i - 1] not in _VOWELS):
            nxt = w[i + 1] if i + 1 < n else ""
            if nxt == "" or nxt not in _VOWELS:
                out.append("ай")
                i += 1
                continue
        if i + 1 < n and w[i] == w[i + 1] and w[i] not in _VOWELS:
            out.append(_SINGLE_SOUND.get(w[i], w[i]))
            i += 2
            continue
        matched = False
        for dg, sound in _DIGRAPHS:
            if w[i:i + len(dg)] == dg:
                out.append(sound)
                i += len(dg)
                matched = True
                break
        if matched:
            continue
        out.append(_SINGLE_SOUND.get(w[i], w[i]))
        i += 1
    return "".join(out)


class WordReplacer:
    def __init__(self, rules_path: str):
        self.rules_path = rules_path
        self.data = {}
        self.flat_rules = {}
        self.load()
        self._seed_builtin_if_needed()

    def load(self):
        if os.path.exists(self.rules_path):
            try:
                with open(self.rules_path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception:
                self.data = {}
        self._build_flat_rules()

    def _seed_builtin_if_needed(self):
        """
        Одноразовая миграция: если категории "builtin" ещё нет в файле —
        записываем туда стартовый набор слов. После этого они — обычные
        записи в JSON, ничем не отличаются от auto/custom, видны и
        редактируются в окне "📖 Словарь". Если пользователь сам удалит
        категорию "builtin" — повторно она не создаётся (уважаем выбор).
        """
        if "builtin" not in self.data:
            self.data["builtin"] = {
                word: {"text": text, "weight": 1.0}
                for word, text in _SEED_DICTIONARY.items()
            }
            self._build_flat_rules()
            self.save()

    def _build_flat_rules(self):
        self.flat_rules = {}
        categories = [c for c in self.data.keys() if c != "meta"]

        def _priority(cat):
            try:
                return _CATEGORY_PRIORITY.index(cat)
            except ValueError:
                return len(_CATEGORY_PRIORITY)  # неизвестные категории — выше custom

        categories.sort(key=_priority)

        for category_name in categories:
            category_data = self.data.get(category_name)
            if not isinstance(category_data, dict):
                continue
            for word, value in category_data.items():
                if isinstance(value, dict):
                    self.flat_rules[word] = value.get("text", "")
                else:
                    self.flat_rules[word] = value

    def save(self):
        with open(self.rules_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def get_words_list(self):
        words = []
        for category_name, category_data in self.data.items():
            if category_name == "meta":
                continue
            if isinstance(category_data, dict):
                words.extend(category_data.keys())
        return sorted(words)

    def get_category(self, word: str):
        for category_name, category_data in self.data.items():
            if category_name == "meta":
                continue
            if isinstance(category_data, dict) and word in category_data:
                return category_name
        return None

    def add_rule(self, word: str, replacement: str, category: str = "custom", weight: float = 1.0):
        word = word.strip()
        old_category = self.get_category(word)
        if old_category and old_category != category:
            del self.data[old_category][word]

        if category not in self.data:
            self.data[category] = {}
        self.data[category][word] = {
            "text": replacement.strip(),
            "weight": float(weight)
        }
        self._build_flat_rules()
        self.save()

    def remove_rule(self, word: str):
        for category in list(self.data.keys()):
            if category == "meta":
                continue
            if word in self.data.get(category, {}):
                del self.data[category][word]
        self._build_flat_rules()
        self.save()

    def apply(self, text: str) -> str:
        sorted_rules = sorted(
            self.flat_rules.items(),
            key=lambda kv: len(kv[0]),
            reverse=True
        )
        for word, replacement in sorted_rules:
            pattern = rf'(?<!\w){re.escape(word)}(?!\w)'
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        def _abbrev_sub(m):
            token = m.group(0)
            if token in self.flat_rules or token.lower() in self.flat_rules:
                return self.flat_rules.get(token, self.flat_rules.get(token.lower()))

            if _looks_like_abbrev(token):
                replacement = _auto_transliterate_abbrev(token)
            elif _looks_like_lowercase_term(token):
                replacement = _transliterate_term_word(token)
            else:
                return token

            self.add_rule(token, replacement, category="auto")
            return replacement

        text = re.sub(r'\b[A-Za-z][A-Za-z0-9]*\b', _abbrev_sub, text)
        return text