"""UUID codec — 16 bytes encoded as two big-endian i64 halves.

Returns / accepts :class:`uuid.UUID` from the stdlib.
"""

from __future__ import annotations

import struct
import uuid as _uuid_stdlib

from minecraft_bot.codec import Reader, Writer

_UUID = _uuid_stdlib.UUID


def read(reader: Reader) -> _UUID:
    """Decode a UUID from 16 bytes (two i64 big-endian halves)."""
    raw = reader.read(16)
    high, low = struct.unpack(">qq", raw)
    return _UUID(int=((high & 0xFFFFFFFFFFFFFFFF) << 64) | (low & 0xFFFFFFFFFFFFFFFF))


def write(value: _UUID, writer: Writer) -> None:
    """Encode a UUID as 16 bytes (two i64 big-endian halves)."""
    bigint = value.int
    high = (bigint >> 64) & 0xFFFFFFFFFFFFFFFF
    low = bigint & 0xFFFFFFFFFFFFFFFF
    # Convert to signed for struct.pack
    if high & (1 << 63):
        high -= 1 << 64
    if low & (1 << 63):
        low -= 1 << 64
    writer.write(struct.pack(">qq", high, low))


__all__ = ["read", "write"]
