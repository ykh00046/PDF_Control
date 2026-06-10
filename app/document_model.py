"""Value objects and per-page caches for the document model.

Split out of the former monolithic ``app/model.py`` (model-restructure).
"""
from typing import Any, Dict, List, Optional

import fitz

from app.text_utils import sanitize_unicode


class WordBox:
    """Represents a word's bounding box and text content."""

    def __init__(self, rect: fitz.Rect, text: str, block: int, line: int, word_no: int) -> None:
        self.rect = rect
        self.text = text
        self.block = block
        self.line = line
        self.word_no = word_no

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rect": list(self.rect), "text": self.text, "block": self.block,
            "line": self.line, "word_no": self.word_no,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "WordBox":
        return WordBox(fitz.Rect(data["rect"]), data["text"], data["block"], data["line"], data["word_no"])


class PageModel:
    """Represents a single page in the document, caching its words."""

    def __init__(self, index: int) -> None:
        self.index = index
        self._words: Optional[List[WordBox]] = None

    def get_words(self, page: fitz.Page) -> List[WordBox]:
        if self._words is None:
            raw_words = page.get_text("words")
            self._words = [
                WordBox(fitz.Rect(w[0], w[1], w[2], w[3]), sanitize_unicode(w[4]), w[5], w[6], w[7])
                for w in raw_words
            ]
        return self._words

    def clear_cache(self) -> None:
        self._words = None
