"""String codec — VarInt-prefixed UTF-8.

Maximum length is 32767 characters per the protocol's overall cap; many
fields cap shorter (e.g., chat 256 chars) — those are enforced by the
packet, not by this codec.
"""

from __future__ import annotations

from minecraft_bot.codec import Reader, Writer, varint
from minecraft_bot.errors import ValueOutOfRange

MAX_LENGTH = 32767


def read(reader: Reader, *, max_length: int = MAX_LENGTH) -> str:
    """Decode a VarInt-prefixed UTF-8 string."""
    n_chars = varint.read(reader)
    if n_chars < 0:
        raise ValueOutOfRange("string.length", n_chars)
    # Wire length is in bytes for the UTF-8 payload, not characters.
    raw = reader.read(n_chars)
    s = raw.decode("utf-8")
    if len(s) > max_length:
        raise ValueOutOfRange("string.length", len(s))
    return s


def write(value: str, writer: Writer, *, max_length: int = MAX_LENGTH) -> None:
    """Encode a string as VarInt-prefixed UTF-8."""
    if len(value) > max_length:
        raise ValueOutOfRange("string.length", len(value))
    raw = value.encode("utf-8")
    varint.write(len(raw), writer)
    writer.write(raw)


__all__ = ["MAX_LENGTH", "read", "write"]
