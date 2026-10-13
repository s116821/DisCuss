"""Encoded product lexicon and normalized whole-token/phrase matching."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import unicodedata
import zlib
from dataclasses import dataclass
from importlib.resources import files

TOKEN = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)


def tokens(text: str) -> list[str]:
    return TOKEN.findall(unicodedata.normalize("NFKC", text).casefold().replace("’", "'"))


def normalize_entry(text: str) -> str:
    parts = tokens(text)
    if not parts or len(text) > 100 or not any(c.isalpha() for c in text):
        raise ValueError("Tracked entries require letters and at most 100 characters")
    return " ".join(parts)


def builtin_words() -> frozenset[str]:
    asset = json.loads(files("discuss").joinpath("assets/lexicon.json").read_text(encoding="utf-8"))
    decoder = zlib.decompressobj()
    raw = decoder.decompress(base64.b85decode(asset["encoded"]), 100001)
    if len(raw) > 100000 or not decoder.eof or hashlib.sha256(raw).hexdigest() != asset["sha256"]:
        raise ValueError("Built-in dictionary integrity check failed")
    data = json.loads(raw)
    if asset["format"] != 1 or not isinstance(data, list) or len(data) > 10000:
        raise ValueError("Invalid built-in dictionary format")
    return frozenset(normalize_entry(word) for word in data)


@dataclass(frozen=True, slots=True)
class Match:
    word: str
    token_start: int
    token_end: int


class Lexicon:
    def __init__(self, use_builtin_list: bool = True, custom_words: list[str] | None = None) -> None:
        words = set(builtin_words()) if use_builtin_list else set()
        words.update(normalize_entry(w) for w in custom_words or [])
        self.words = frozenset(words)
        self.phrases = sorted(((tuple(w.split()), w) for w in words), key=lambda p: (-len(p[0]), p[1]))
        self.revision = hashlib.sha256(json.dumps(sorted(words), ensure_ascii=False).encode()).hexdigest()

    def matches(self, text: str) -> list[Match]:
        parts = tokens(text)
        result = []
        index = 0
        while index < len(parts):
            for phrase, word in self.phrases:
                if tuple(parts[index : index + len(phrase)]) == phrase:
                    result.append(Match(word, index, index + len(phrase)))
                    index += len(phrase)
                    break
            else:
                index += 1
        return result
