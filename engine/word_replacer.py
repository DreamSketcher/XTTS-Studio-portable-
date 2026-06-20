# engine/word_replacer.py

import json
import os
import re


class WordReplacer:
    def __init__(self, rules_path: str):
        self.rules_path = rules_path
        self.rules = {}
        self.load()

    def load(self):
        if os.path.exists(self.rules_path):
            try:
                with open(self.rules_path, "r", encoding="utf-8") as f:
                    self.rules = json.load(f)
            except Exception:
                self.rules = {}

    def save(self):
        with open(self.rules_path, "w", encoding="utf-8") as f:
            json.dump(self.rules, f, ensure_ascii=False, indent=2)

    def add_rule(self, word: str, replacement: str):
        self.rules[word.strip()] = replacement.strip()
        self.save()

    def remove_rule(self, word: str):
        if word in self.rules:
            del self.rules[word]
            self.save()

    def apply(self, text: str) -> str:
        for word, replacement in self.rules.items():
            pattern = rf'(?<!\w){re.escape(word)}(?!\w)'
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text