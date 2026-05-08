"""BitSet codec — VarInt-prefixed array of i64 (long).

The wire format is the count of i64 longs followed by that many
big-endian i64 values. Bit ``i`` corresponds to ``longs[i // 64]`` bit
``(i % 64)``.

Returns / accepts a ``set[int]`` of the indices of set bits — sparse
representation, easy for callers to inspect. Encoding chooses the
smallest long array that holds all set bits.
"""

from __future__ import annotations

import struct

from minecraft_bot.codec import Reader, Writer, varint
from minecraft_bot.errors import ValueOutOfRange


def read(reader: Reader) -> set[int]:
    """Decode a BitSet into ``{i: bit i is set}``."""
    n_longs = varint.read(reader)
    if n_longs < 0:
        raise ValueOutOfRange("bitset.length", n_longs)
    result: set[int] = set()
    for i in range(n_longs):
        (chunk,) = struct.unpack(">q", reader.read(8))
        # chunk is signed; mask to 64-bit unsigned for bit inspection
        u = chunk & 0xFFFFFFFFFFFFFFFF
        base = i * 64
        for j in range(64):
            if u & (1 << j):
                result.add(base + j)
    return result


def write(value: set[int], writer: Writer) -> None:
    """Encode ``{indices}`` into the smallest long array that holds them."""
    if not value:
        varint.write(0, writer)
        return
    if any(bit < 0 for bit in value):
        raise ValueOutOfRange("bitset.bit", min(value))
    n_longs = (max(value) // 64) + 1
    longs = [0] * n_longs
    for bit in value:
        longs[bit // 64] |= 1 << (bit % 64)
    varint.write(n_longs, writer)
    for chunk in longs:
        # Convert unsigned chunk back to signed for big-endian i64
        if chunk & (1 << 63):
            chunk -= 1 << 64
        writer.write(struct.pack(">q", chunk))


__all__ = ["read", "write"]
