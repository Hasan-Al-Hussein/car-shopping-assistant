"""Finite competitor-name suppression for assistant prose, never source-data mutation."""

import html
import re
import unicodedata
from urllib.parse import unquote

_NAMES = re.compile(r"dubicars|yallamotor|autotrader|cars24")
_ENCODED = re.compile(r"(?:%[0-9a-fA-F]{2})+|&#(?:[0-9]{1,10}|[xX][0-9a-fA-F]{1,8});|"
                      r"&[a-zA-Z]+;|\\u[0-9a-fA-F]{4}|\\U[0-9a-fA-F]{8}")


def safe_assistant_text(text: str) -> str:
    """Replace reviewed labels, preserving every unrelated character and original DTO.

    Four bounded decoding passes cover common nested escapes. This is a finite label
    policy, not recognition of every platform, language or possible obfuscation.
    """
    viewed = text
    spans = [(index, index + 1) for index in range(len(text))]
    for _ in range(4):
        chunks: list[str] = []
        mapped: list[tuple[int, int]] = []
        cursor = 0
        for match in _ENCODED.finditer(viewed):
            start, end = match.span()
            chunks.append(viewed[cursor:start])
            mapped.extend(spans[cursor:start])
            token = match.group()
            if token.startswith("%"):
                decoded = unquote(token)
            elif token.startswith("\\"):
                number = int(token[2:], 16)
                decoded = chr(number) if number <= 0x10FFFF else token
            else:
                decoded = html.unescape(token)
            chunks.append(decoded)
            widths = (
                [len(char.encode("utf-8")) * 3 for char in decoded] if token.startswith("%") else []
            )
            if token.startswith("%") and sum(widths) == len(token):
                offset = start
                for width in widths:
                    mapped.append((spans[offset][0], spans[offset + width - 1][1]))
                    offset += width
            else:
                mapped.extend([(spans[start][0], spans[end - 1][1])] * len(decoded))
            cursor = end
        chunks.append(viewed[cursor:])
        mapped.extend(spans[cursor:])
        updated = "".join(chunks)
        if updated == viewed:
            break
        viewed, spans = updated, mapped
    normalized: list[str] = []
    positions: list[tuple[int, int]] = []
    for char, span in zip(viewed, spans, strict=True):
        for part in unicodedata.normalize("NFKC", char).casefold():
            if part.isalnum():
                normalized.append(part)
                positions.append(span)
            elif part not in " \t\r\n-._/\\" and unicodedata.category(part) not in {"Cf", "Mn"}:
                normalized.append("|")
                positions.append(span)
    ranges: list[tuple[int, int]] = []
    for match in _NAMES.finditer("".join(normalized)):
        start, end = positions[match.start()][0], positions[match.end() - 1][1]
        if ranges and start <= ranges[-1][1]:
            ranges[-1] = (ranges[-1][0], max(end, ranges[-1][1]))
        else:
            ranges.append((start, end))
    for start, end in reversed(ranges):
        # Five characters never expands the shortest reviewed name or the answer limit.
        text = text[:start] + "[...]" + text[end:]
    return text
