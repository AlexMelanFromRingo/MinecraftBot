"""Primitive codec layer: byte-stream readers/writers + per-type codecs.

Each codec lives in its own module:

- ``varint``         signed 32-bit, 1–5 bytes
- ``varlong``        signed 64-bit, 1–10 bytes
- ``string``         VarInt-prefixed UTF-8
- ``uuid``           two big-endian i64 halves
- ``position``       packed 64-bit (26-12-26 signed; x, y, z)
- ``identifier``     namespaced string (``namespace:path``)
- ``bitset``         VarInt-prefixed array of i64
- ``nbt``            network NBT (no root name, all 13 tag types)
- ``slot``           ``Optional[SlotData]`` (item id + count + NBT)
- ``chat_component`` JSON string

All public types and functions are re-exported here for convenience::

    from minecraft_bot.codec import Reader, Writer, varint, nbt
"""

from __future__ import annotations

from minecraft_bot.errors import IncompleteRead

__all__ = ["Reader", "Writer"]


class Reader:
    """A non-rewindable byte stream reader over an in-memory buffer.

    Codecs consume bytes via :meth:`read` and inspect the remaining count
    via :meth:`remaining`. :meth:`peek` looks without advancing.

    Designed for synchronous, in-memory operation; the framer is
    responsible for assembling complete packets before handing them to
    a Reader.
    """

    __slots__ = ("_data", "_pos")

    def __init__(self, data: bytes | bytearray | memoryview) -> None:
        self._data = bytes(data) if not isinstance(data, bytes) else data
        self._pos = 0

    def read(self, n: int) -> bytes:
        """Return the next ``n`` bytes and advance the cursor.

        Raises :class:`~minecraft_bot.errors.IncompleteRead` if fewer than
        ``n`` bytes remain.
        """
        if n < 0:
            raise ValueError(f"Reader.read: negative length {n}")
        end = self._pos + n
        if end > len(self._data):
            raise IncompleteRead(requested=n, available=len(self._data) - self._pos)
        result = self._data[self._pos:end]
        self._pos = end
        return result

    def peek(self, n: int) -> bytes:
        """Return the next up-to ``n`` bytes WITHOUT advancing.

        Returns whatever is available, even if fewer than ``n`` bytes remain
        (useful for VarInt scanning where the caller doesn't know the size
        upfront).
        """
        if n < 0:
            raise ValueError(f"Reader.peek: negative length {n}")
        return self._data[self._pos:self._pos + n]

    def remaining(self) -> int:
        return len(self._data) - self._pos

    def position(self) -> int:
        return self._pos

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f"Reader(pos={self._pos}, len={len(self._data)})"


class Writer:
    """A growable byte-buffer writer.

    Codecs accumulate bytes via :meth:`write`; the final byte string is
    obtained via :meth:`bytes`.
    """

    __slots__ = ("_buf",)

    def __init__(self) -> None:
        self._buf = bytearray()

    def write(self, b: bytes) -> None:
        """Append raw bytes to the buffer."""
        self._buf.extend(b)

    def bytes(self) -> bytes:
        """Return the accumulated bytes as an immutable :class:`bytes`."""
        return bytes(self._buf)

    def __len__(self) -> int:
        return len(self._buf)

    def __repr__(self) -> str:
        return f"Writer(len={len(self._buf)})"
