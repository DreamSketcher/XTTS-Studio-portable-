import re
from num2words import num2words


class TextNormalizer:
    ORDINALS = {
        1: "первое", 2: "второе", 3: "третье", 4: "четвёртое",
        5: "пятое", 6: "шестое", 7: "седьмое", 8: "восьмое",
        9: "девятое", 10: "десятое", 11: "одиннадцатое",
        12: "двенадцатое", 13: "тринадцатое", 14: "четырнадцатое",
        15: "пятнадцатое", 16: "шестнадцатое", 17: "семнадцатое",
        18: "восемнадцатое", 19: "девятнадцатое", 20: "двадцатое",
    }

    def _ordinal_neuter(self, n: int) -> str:
        """
        Возвращает порядковое числительное в среднем роде.
        Сначала проверяет словарь, затем генерирует через num2words
        и корректирует окончание на средний род.
        """
        cached = self.ORDINALS.get(n)
        if cached is not None:
            return cached

        # num2words возвращает мужской род: "двадцать первый"
        word = num2words(n, lang="ru", to="ordinal")

        # Корректируем окончание на средний род:
        # -ый → -ое, -ий → -ье, -ой → -ое
        if word.endswith("ый"):
            word = word[:-2] + "ое"
        elif word.endswith("ий"):
            word = word[:-2] + "ье"
        elif word.endswith("ой"):
            word = word[:-2] + "ое"

        return word

    def normalize(self, text: str) -> str:
        if not text:
            return ""

        # =========================
        # BASIC CLEANUP
        # =========================
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)

        text = text.replace("—", ". ")

        # проценты: 87% → 87 процентов
        text = re.sub(r"(\d+)\s*%", r"\1 процентов", text)

        text = re.sub(r"!{2,}", "!", text)
        text = re.sub(r"\?{2,}", "?", text)
        text = re.sub(r",{2,}", ",", text)

        text = re.sub(r"([A-ZА-Я]{2,}),\s*([A-ZА-Я]{2,})", r"\1. \2", text)

        text = "\n".join(line.strip() for line in text.split("\n"))
        text = re.sub(r"\n{2,}", "\n", text)

        text = re.sub(r"(\.)([A-ZА-ЯЁ])", r"\1 \2", text)

        text = re.sub(r"\s+", " ", text).strip()
        

        # =========================
        # NUMBERS TO WORDS
        # =========================

        # 1. Нумерованные списки: "1)" → "первое,"
        text = re.sub(
            r"\b(\d+)\)",
            lambda m: self._ordinal_neuter(int(m.group(1))) + ",",
            text,
        )

        # 2. Функция для замены обычных чисел
        def replace_number(match):
            num_str = match.group(0).replace(" ", "")
            try:
                num = int(num_str)
                return num2words(num, lang="ru")
            except ValueError:
                try:
                    num = float(num_str.replace(",", "."))
                    return num2words(num, lang="ru")
                except Exception:
                    return num_str
            except Exception:
                return num_str

        # проценты: 87% → 87 процентов
        text = re.sub(r"(\d+)\s*%", r"\1 процентов", text)

        # дробные через точку → через запятую
        text = re.sub(r"\b(\d+)\.(\d+)\b", r"\1,\2", text)

        # 3. Дробные числа через запятую: 3,14
        text = re.sub(r"\b\d+,\d+\b", replace_number, text)

        # 4. Целые числа
        text = re.sub(r"\b\d[\d ]{0,30}\d\b|\b\d\b", replace_number, text)

        # =========================
        # SAFE CHARACTER FILTER
        # =========================
        # Явно добавлены ёЁ, чтобы не зависеть от поведения \w
        text = re.sub(
            r"[^\w\s.,!?:;\"'\-()\nа-яА-ЯёЁa-zA-Z0-9]",
            "",
            text,
        )

        # =========================
        # LINE CLEANUP
        # =========================
        text = "\n".join(line.strip() for line in text.split("\n"))
        text = re.sub(r"\n{2,}", "\n", text)

        # =========================
        # FINAL NORMALIZATION
        # =========================
        text = text.strip()
        text = re.sub(r"[.,]+$", "", text)
        if text and text[-1] not in ".!?":
            text += "."

        return text