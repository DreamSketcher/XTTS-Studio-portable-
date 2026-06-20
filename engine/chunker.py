import re

class TextChunker:
    def __init__(self):
        self.max_chunk_size = 150
        self.min_chunk_size = 40

    def chunk_text(self, text):
        sentences = re.split(r'(?<=[.!?])\s+', text)
        raw_chunks = []
        for sentence in sentences:
            raw_chunks.extend(self._split_long_sentence(sentence))
        merged = self._merge_short_chunks(raw_chunks)
        result = []
        for c in merged:
            c = c.strip()
            if c and c[-1] not in ".!?":
                c += "."
            result.append(c)
        return [c for c in result if c]

    def _split_long_sentence(self, sentence):
        if len(sentence) <= self.max_chunk_size:
            return [sentence]

        parts = re.split(r'[,;:]', sentence)
        result = []
        buffer = ""
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if len(buffer) + len(part) + 2 < self.max_chunk_size:
                buffer = (buffer + ", " + part).strip(", ")
            else:
                if buffer:
                    result.append(buffer.strip())
                buffer = part
        if buffer:
            result.append(buffer.strip())
        return result

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