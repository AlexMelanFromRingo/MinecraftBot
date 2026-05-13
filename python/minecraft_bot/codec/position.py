"""Position codec — packed 64-bit big-endian: 26-bit x, 26-bit z, 12-bit y, all signed.

Wire encoding (big-endian u64)::

    val = ((x & 0x3FFFFFF) << 38) | ((z & 0x3FFFFFF) << 12) | (y & 0xFFF)

Decoding sign-extends each component back to a Python int. Returns and
accepts a 3-tuple ``(x, y, z)``.
"""

from __future__ import annotations

import struct

from minecraft_bot.codec import Reader, Writer
from minecraft_bot.errors import ValueOutOfRange

X_MIN, X_MAX = -(1 << 25), (1 << 25) - 1
Z_MIN, Z_MAX = -(1 << 25), (1 << 25) - 1
Y_MIN, Y_MAX = -(1 << 11), (1 << 11) - 1


def _sign_extend(value: int, bits: int) -> int:
    mask = (1 << bits) - 1
    value &= mask
    if value & (1 << (bits - 1)):
        value -= 1 << bits
    return value


def read(reader: Reader) -> tuple[int, int, int]:
    """Decode a Position from 8 big-endian bytes. Returns ``(x, y, z)``."""
    (val,) = struct.unpack(">Q", reader.read(8))
    x = _sign_extend((val >> 38) & 0x3FFFFFF, 26)
    z = _sign_extend((val >> 12) & 0x3FFFFFF, 26)
    y = _sign_extend(val & 0xFFF, 12)
    return (x, y, z)


def write(value: tuple[int, int, int], writer: Writer) -> None:
    """Encode ``(x, y, z)`` into 8 big-endian bytes."""
    x, y, z = value
    if not (X_MIN <= x <= X_MAX):
        raise ValueOutOfRange("position.x", x)
    if not (Y_MIN <= y <= Y_MAX):
        raise ValueOutOfRange("position.y", y)
    if not (Z_MIN <= z <= Z_MAX):
        raise ValueOutOfRange("position.z", z)
    val = ((x & 0x3FFFFFF) << 38) | ((z & 0x3FFFFFF) << 12) | (y & 0xFFF)
    writer.write(struct.pack(">Q", val))


__all__ = ["X_MAX", "X_MIN", "Y_MAX", "Y_MIN", "Z_MAX", "Z_MIN", "read", "write"]
