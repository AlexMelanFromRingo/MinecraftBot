"""VarLong codec — signed 64-bit, variable-length, 1–10 bytes.

Same encoding shape as VarInt but with an i64 result and a 10-byte cap.
"""

from __future__ import annotations

from minecraft_bot.codec import Reader, Writer
from minecraft_bot.errors import OversizedVarInt, ValueOutOfRange

_INT64_MIN = -(1 << 63)
_INT64_MAX = (1 << 63) - 1
MAX_BYTES = 10


def read(reader: Reader) -> int:
    """Decode a VarLong from ``reader``. Returns a Python int in i64 range."""
    result = 0
    for i in range(MAX_BYTES):
        b = reader.read(1)[0]
        result |= (b & 0x7F) << (7 * i)
        if (b & 0x80) == 0:
            if result & (1 << 63):
                result -= (1 << 64)
            return result
    raise OversizedVarInt(byte_count=MAX_BYTES + 1)


def write(value: int, writer: Writer) -> None:
    """Encode an i64 as VarLong into ``writer``."""
    if not (_INT64_MIN <= value <= _INT64_MAX):
        raise ValueOutOfRange("varlong", value)
    u = value & 0xFFFFFFFFFFFFFFFF
    out = bytearray()
    while True:
        if (u & ~0x7F) == 0:
            out.append(u)
            break
        out.append((u & 0x7F) | 0x80)
        u >>= 7
    writer.write(bytes(out))


__all__ = ["read", "write", "MAX_BYTES"]
