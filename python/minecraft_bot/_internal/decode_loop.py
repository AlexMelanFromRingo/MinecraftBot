"""Async decode-and-dispatch pipeline scaffold.

Per R-07, the inbound pipeline is two stages:

1. **Framer stage** — owns the socket, accumulates bytes, emits
   :class:`RawPacket` objects (one per complete frame) into a bounded
   ``asyncio.Queue``.
2. **Decode-and-dispatch stage** — pulls from the queue, looks up the
   packet class in the :class:`~minecraft_bot.protocol.v763.registry.CodecRegistry`,
   decodes, then synchronously fans out to subscribers and updates the
   :class:`Connection`'s state view.

Critical-path packets (KeepAlive auto-reply, SynchronizePlayerPosition
auto-confirm) are handled INSIDE the decode loop, before subscriber
fan-out, so a slow user hook cannot starve protocol heartbeats
(SC-009 + spec edge cases).

This file is the **scaffold** for the loop. The actual
``Connection`` wiring (sockets, hook fan-out, auto-reply) lands in
Phase 3 (US1) where the :class:`Connection` class is implemented.
For Phase 2 we expose the data structures and a synchronous helper
that exercises the framer-to-registry path against a packet body.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader
from minecraft_bot.errors import IncompleteRead, UnknownPacketId
from minecraft_bot.protocol.v763.registry import CodecRegistry
from minecraft_bot.protocol.v763.states import ConnectionState, Direction


@dataclass(frozen=True, slots=True)
class RawPacket:
    """A framed packet's body before the registry has decoded it.

    Internal type. The public API exposes only typed packet objects.
    """

    state: ConnectionState
    direction: Direction
    packet_id: int
    payload: bytes


def split_body(body: bytes) -> tuple[int, bytes]:
    """Peel the leading packet-id VarInt off a framed body.

    Returns ``(packet_id, payload_bytes)``. The payload bytes are the
    portion the per-packet ``decode`` function consumes.
    """
    # Inline a small VarInt read to avoid importing the codec layer.
    result = 0
    pos = 0
    for i in range(5):
        if pos >= len(body):
            raise IncompleteRead(requested=1, available=0)
        b = body[pos]
        pos += 1
        result |= (b & 0x7F) << (7 * i)
        if (b & 0x80) == 0:
            if result & (1 << 31):
                result -= 1 << 32
            return (result, body[pos:])
    # 5 bytes consumed, continuation still set on the 5th — malformed.
    from minecraft_bot.errors import OversizedVarInt
    raise OversizedVarInt(byte_count=5)


def decode_one(
    body: bytes,
    state: ConnectionState,
    direction: Direction,
    registry: CodecRegistry,
) -> object:
    """Decode a single framed body into a typed packet via ``registry``.

    Useful for unit tests and replay; the live :class:`Connection`
    decode loop wraps this call.

    Raises :class:`UnknownPacketId` if the packet id is not registered
    for the (state, direction) tuple, or any codec-level
    :class:`~minecraft_bot.errors.DecodeError` from the per-packet
    ``decode`` function.
    """
    packet_id, payload = split_body(body)
    decoder = registry.decoder(state, direction, packet_id)
    if decoder is None:  # pragma: no cover — registry.decoder raises instead
        raise UnknownPacketId(state=state, direction=direction, id=packet_id)
    reader = Reader(payload)
    return decoder(reader)  # type: ignore[operator]


__all__ = ["RawPacket", "decode_one", "split_body"]
