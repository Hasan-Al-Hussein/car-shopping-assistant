"""Bounded text-only representations. No aliases, fact extraction or HTML output."""

import math
import re
import unicodedata
from dataclasses import dataclass, field
from html import unescape
from html.entities import html5
from html.parser import HTMLParser
from typing import Literal

from app.inventory.import_reader import TEXT_LIMITS, SourceCell

TextState = Literal["informative", "uninformative", "unsupported", "withheld"]
TEXT_FIELDS = ("year", "make", "model", "trim", "title", "description")
MAX_MARKUP_EVENTS = 4096
FORMATTING_TAGS = frozenset(
    (
        "a",
        "b",
        "strong",
        "em",
        "i",
        "u",
        "span",
        "div",
        "p",
        "br",
        "ul",
        "ol",
        "li",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "table",
        "tbody",
        "thead",
        "tr",
        "th",
        "td",
    )
)
BLOCK_TAGS = FORMATTING_TAGS - {"a", "b", "strong", "em", "i", "u", "span"}
SIMPLE_START_TAG = re.compile(r"<[A-Za-z][A-Za-z0-9]*\s*/?>")
SIMPLE_END_TAG = re.compile(r"</[A-Za-z][A-Za-z0-9]*\s*>")


class _UnsafeRepresentation(ValueError):
    pass


class _PlainText(HTMLParser):
    """Decode entities once; block tags become word boundaries.

    Unknown/semantic tags, comments, declarations and processing instructions
    withhold the whole derived field. Never drop just an uncertain qualifier.
    Malformed tag residue is retained as literal text by HTMLParser.close().
    """

    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=False)
        self.source = source
        self.line_offsets = [0, *(index + 1 for index, char in enumerate(source) if char == "\n")]
        self.parts: list[str | None] = []
        self.events = 0
        self.had_markup = False

    def _append(self, value: str | None) -> None:
        self.events += 1
        if self.events > MAX_MARKUP_EVENTS:
            raise _UnsafeRepresentation("MARKUP_LIMIT")
        self.parts.append(value)

    def handle_data(self, data: str) -> None:
        self._append(data)

    def _entity(self, name: str, *, numeric: bool) -> None:
        line, column = self.getpos()
        offset = self.line_offsets[line - 1] + column
        length = len(name) + (2 if numeric else 1)
        terminated = self.source[offset + length : offset + length + 1] == ";"
        raw = self.source[offset : offset + length + int(terminated)]
        # Do not turn an ambiguous '&not warranty' into a different assertion.
        # Only complete known entities decode, and decoded output is never reparsed.
        if terminated and (numeric or name + ";" in html5):
            decoded = unescape(raw)
            if not decoded or "\ufffd" in decoded:
                raise _UnsafeRepresentation("INVALID_ENTITY")
            self._append(decoded)
        else:
            self._append(raw)

    def handle_entityref(self, name: str) -> None:
        self._entity(name, numeric=False)

    def handle_charref(self, name: str) -> None:
        self._entity(name, numeric=True)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if attrs or not SIMPLE_START_TAG.fullmatch(self.get_starttag_text() or ""):
            raise _UnsafeRepresentation("UNSUPPORTED_MARKUP")
        self._tag(tag)

    def _tag(self, tag: str) -> None:
        if tag not in FORMATTING_TAGS:
            raise _UnsafeRepresentation("UNSUPPORTED_MARKUP")
        self.had_markup = True
        self._append(" " if tag in BLOCK_TAGS else None)

    def handle_endtag(self, tag: str) -> None:
        self._tag(tag)

    def plain_text(self) -> str:
        # Inline tags cannot safely decide between n<b>o and no<b>warranty.
        # Preserve punctuation around inline tags; withhold ambiguous word joins.
        right: list[str] = [""] * (len(self.parts) + 1)
        for index in range(len(self.parts) - 1, -1, -1):
            part = self.parts[index]
            right[index] = part[0] if part else right[index + 1]
        left = ""
        output: list[str] = []
        for index, part in enumerate(self.parts):
            if part is None:
                following = right[index + 1]
                if _word_char(left) and _word_char(following):
                    raise _UnsafeRepresentation("AMBIGUOUS_INLINE_BOUNDARY")
            elif part:
                output.append(part)
                left = part[-1]
        return "".join(output)

    def handle_comment(self, data: str) -> None:
        raise _UnsafeRepresentation("UNSUPPORTED_MARKUP")

    def handle_decl(self, decl: str) -> None:
        raise _UnsafeRepresentation("UNSUPPORTED_MARKUP")

    def handle_pi(self, data: str) -> None:
        raise _UnsafeRepresentation("UNSUPPORTED_MARKUP")

    def unknown_decl(self, data: str) -> None:
        raise _UnsafeRepresentation("UNSUPPORTED_MARKUP")


@dataclass(frozen=True)
class TextRepresentation:
    """Plain text for escaped text rendering, never an HTML-safety wrapper.

    'informative' means non-placeholder text, not a verified vehicle fact. Exact
    evidence spans must be taken from the original SourceCell, never these offsets.
    """

    state: TextState
    reason: str | None
    display: str | None = field(repr=False)
    search: str | None = field(repr=False)
    transformations: tuple[str, ...] = ()


def _unavailable(state: TextState, reason: str) -> TextRepresentation:
    return TextRepresentation(state, reason, None, None)


def _word_char(value: str) -> bool:
    return bool(value) and (
        value.isalnum() or value == "_" or unicodedata.category(value).startswith("M")
    )


def normalize_text(cell: SourceCell) -> TextRepresentation:
    if cell.field not in TEXT_FIELDS:
        raise ValueError("TEXT_FIELD_UNSUPPORTED")
    value = cell.value
    if value is None:
        return _unavailable("uninformative", "NOT_STATED")
    if cell.data_type in {"f", "e"} or isinstance(value, bool):
        return _unavailable("unsupported", "SOURCE_TYPE_UNSUPPORTED")
    if isinstance(value, str) and not value.strip():
        return _unavailable("uninformative", "NOT_STATED")
    changes: list[str] = []
    if isinstance(value, (int, float)) and cell.field in {"year", "model", "trim"}:
        if abs(value) > 2**53 - 1 or not math.isfinite(value) or int(value) != value:
            return _unavailable("unsupported", "NUMERIC_LABEL_UNSUPPORTED")
        if cell.field == "year" and not 1000 <= value <= 9999:
            return _unavailable("unsupported", "YEAR_UNSUPPORTED")
        original_text = str(int(value))
        changes.append("NUMERIC_LABEL")
    elif isinstance(value, str):
        if cell.field == "year":
            return _unavailable("unsupported", "SOURCE_TYPE_UNSUPPORTED")
        original_text = value
    else:
        return _unavailable("unsupported", "SOURCE_TYPE_UNSUPPORTED")

    limit = TEXT_LIMITS.get(cell.field, 200)
    if len(original_text) > limit:
        return _unavailable("withheld", "TEXT_TOO_LONG")
    if any(
        unicodedata.category(char) in {"Cc", "Cs"} and char not in "\t\r\n"
        for char in original_text
    ):
        return _unavailable("withheld", "CONTROL_CHARACTER")
    parser = _PlainText(original_text)
    try:
        # HTMLParser drops </> and trailing material in </b qualifier> silently.
        # Detect those before callbacks, which cannot account for discarded text.
        if any(
            not SIMPLE_END_TAG.match(original_text, match.start())
            for match in re.finditer(r"</", original_text)
        ):
            raise _UnsafeRepresentation("MALFORMED_MARKUP")
        parser.feed(original_text)
        parser.close()
        plain = parser.plain_text()
    except _UnsafeRepresentation as error:
        return _unavailable("withheld", str(error))
    except (ValueError, AssertionError):
        return _unavailable("withheld", "MALFORMED_MARKUP")
    if any(unicodedata.category(char) in {"Cc", "Cs"} and char not in "\t\r\n" for char in plain):
        return _unavailable("withheld", "CONTROL_CHARACTER")
    if parser.had_markup:
        changes.append("FORMATTING_MARKUP_REMOVED")
    if plain != original_text:
        changes.append("PLAIN_TEXT_TRANSFORMED")
    display = " ".join(plain.split())
    if len(display) > limit:
        return _unavailable("withheld", "TEXT_TOO_LONG")
    if display != plain:
        changes.append("WHITESPACE_COLLAPSED")
    search = display.casefold()
    if search != display:
        changes.append("SEARCH_CASEFOLDED")
    if not display:
        return _unavailable("uninformative", "NOT_STATED")
    if (cell.field == "description" and display == ".") or (
        cell.field == "trim" and search == "other"
    ):
        return TextRepresentation("uninformative", "PLACEHOLDER", display, None, tuple(changes))
    return TextRepresentation("informative", None, display, search, tuple(changes))
