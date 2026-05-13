"""FIFO write lock for serverbound packets.

Per FR-013a, all serverbound writes from a single ``Connection`` MUST
appear on the wire in strict FIFO order — the order in which
``await connection.send(...)`` calls return must match wire order.

Implementation: a single ``asyncio.Lock`` per ``Connection``. Encode
work happens OUTSIDE the lock (no I/O contention while CPU work runs);
the lock guards only the framer-encode + writer-write + drain
critical section.

This module is intentionally tiny — the lock semantics are stdlib
``asyncio.Lock``. The wrapper here only adds a friendly ``__repr__``
and a clear name for tracing.
"""

from __future__ import annotations

import asyncio


class WriteLock:
    """Per-Connection FIFO write guard.

    Use as an async context manager::

        async with self._write_lock:
            self._writer.write(framed)
            await self._writer.drain()
    """

    __slots__ = ("_lock", "_owner")

    def __init__(self, owner_repr: str = "Connection") -> None:
        self._lock = asyncio.Lock()
        self._owner = owner_repr

    async def __aenter__(self) -> WriteLock:
        await self._lock.acquire()
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        self._lock.release()

    def locked(self) -> bool:
        return self._lock.locked()

    def __repr__(self) -> str:
        return f"WriteLock({self._owner}, locked={self._lock.locked()})"


__all__ = ["WriteLock"]
