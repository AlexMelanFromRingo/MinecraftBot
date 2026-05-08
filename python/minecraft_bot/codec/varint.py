"""VarInt codec — signed 32-bit, variable-length, 1–5 bytes.

Wire format: little-endian-by-7-bit groups, MSB of each byte signals
continuation, low 7 bits carry data. After 5 bytes the next bit must be a
terminator; if not, the stream is malformed and :class:`OversizedVarInt`
is raised. Negative numbers are encoded as their two's-complement u32
representation.

See ``data-model.md`` E-5 and ``research.md`` R-02.
"""

from __future__ import annotations

from minecraft_bot.codec import Reader, Writer
from minecraft_bot.errors import OversizedVarInt, ValueOutOfRange

_INT32_MIN = -(1 << 31)
_INT32_MAX = (1 << 31) - 1
MAX_BYTES = 5


def read(reader: Reader) -> int:
    """Decode a VarInt from ``reader``. Returns a Python int in i32 range."""
    result = 0
    for i in range(MAX_BYTES):
        b = reader.read(1)[0]
        result |= (b & 0x7F) << (7 * i)
        if (b & 0x80) == 0:
            # Sign-extend from bit 31 since the wire format is two's complement i32.
            if result & (1 << 31):
                result -= (1 << 32)
            return result
    # 5 bytes consumed and continuation bit still set on the last one.
    raise OversizedVarInt(byte_count=MAX_BYTES + 1)


def write(value: int, writer: Writer) -> None:
    """Encode an i32 as VarInt into ``writer``.

    Raises :class:`ValueOutOfRange` if ``value`` is outside i32.
    """
    if not (_INT32_MIN <= value <= _INT32_MAX):
        raise ValueOutOfRange("varint", value)
    # Convert to unsigned 32-bit for the bit dance.
    u = value & 0xFFFFFFFF
    out = bytearray()
    while True:
        if (u & ~0x7F) == 0:
            out.append(u)
            break
        out.append((u & 0x7F) | 0x80)
        u >>= 7
    writer.write(bytes(out))


def encoded_size(value: int) -> int:
    """How many bytes :func:`write` would emit for ``value``."""
    if not (_INT32_MIN <= value <= _INT32_MAX):
        raise ValueOutOfRange("varint", value)
    u = value & 0xFFFFFFFF
    if u < 0x80:
        return 1
    if u < 0x4000:
        return 2
    if u < 0x200000:
        return 3
    if u < 0x10000000:
        return 4
    return 5


__all__ = ["read", "write", "encoded_size", "MAX_BYTES"]
