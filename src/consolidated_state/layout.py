from __future__ import annotations

from dataclasses import dataclass

import fitz


@dataclass(frozen=True)
class LayoutWord:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str

    @property
    def center_x(self) -> float:
        return (self.x0 + self.x1) / 2


@dataclass(frozen=True)
class LayoutRow:
    y: float
    words: tuple[LayoutWord, ...]

    @property
    def text(self) -> str:
        return " ".join(word.text for word in self.words)


@dataclass(frozen=True)
class PageLayout:
    page_number: int
    width: float
    height: float
    rows: tuple[LayoutRow, ...]


@dataclass(frozen=True)
class DocumentLayout:
    pages: tuple[PageLayout, ...]


def _group_words_into_rows(raw_words: list[tuple], tolerance: float = 2.2) -> tuple[LayoutRow, ...]:
    ordered = sorted(raw_words, key=lambda word: (word[1], word[0]))
    working: list[dict[str, object]] = []

    for raw in ordered:
        word = LayoutWord(float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3]), str(raw[4]))
        matched = None

        for row in working[-8:]:
            if abs(float(row["y"]) - word.y0) <= tolerance:
                matched = row
                break

        if matched is None:
            working.append({"y": word.y0, "words": [word]})
        else:
            words = matched["words"]
            assert isinstance(words, list)
            words.append(word)
            matched["y"] = (float(matched["y"]) + word.y0) / 2

    rows: list[LayoutRow] = []
    for row in working:
        words = row["words"]
        assert isinstance(words, list)
        words.sort(key=lambda word: word.x0)
        rows.append(LayoutRow(y=float(row["y"]), words=tuple(words)))

    return tuple(rows)


def extract_document_layout(pdf_bytes: bytes) -> DocumentLayout:
    pages: list[PageLayout] = []

    with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
        if document.needs_pass:
            return DocumentLayout(pages=())

        for page_number, page in enumerate(document, start=1):
            pages.append(
                PageLayout(
                    page_number=page_number,
                    width=float(page.rect.width),
                    height=float(page.rect.height),
                    rows=_group_words_into_rows(page.get_text("words")),
                )
            )

    return DocumentLayout(pages=tuple(pages))
