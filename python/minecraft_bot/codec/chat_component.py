"""Chat component codec — JSON-encoded chat message structure.

Wire format is a regular VarInt-prefixed UTF-8 string carrying a JSON
document. The framework keeps it as a raw string at this layer; higher
levels can parse the JSON if they need structured access (the JSON
shape is large, varies between text/translatable/keybind/score
components, and is best handled by callers who know what they want).

Maximum length is 262144 bytes per the protocol (chat components can
be enormous because of nested hover/click events).
"""

from __future__ import annotations

from minecraft_bot.codec import Reader, Writer, string

MAX_LENGTH = 262144  # bytes; protocol cap for chat components


def read(reader: Reader) -> str:
    """Decode the JSON string. Returns the raw JSON; caller may ``json.loads``
    it if structured access is needed."""
    return string.read(reader, max_length=MAX_LENGTH)


def write(value: str, writer: Writer) -> None:
    """Encode a JSON string. ``value`` must already be valid JSON; this codec
    does not validate JSON shape — only encodes the bytes."""
    string.write(value, writer, max_length=MAX_LENGTH)


__all__ = ["MAX_LENGTH", "read", "write"]
