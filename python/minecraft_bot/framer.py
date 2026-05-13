"""Wire framer — length-prefix + optional zlib-threshold compression.

This module implements the Minecraft Java Edition packet frame format
(R-02 / FR-004 / FR-011). It is purely synchronous and stateful: feed
arbitrary chunks of TCP bytes, then call :meth:`Framer.try_extract`
repeatedly to pull complete packet bodies out.

Wire format (compression disabled, ``threshold = -1``)::

    [varint:packet_length] [packet_length bytes: id_varint + payload]

Wire format (compression enabled, ``threshold >= 0``)::

    [varint:packet_length] [packet_length bytes: data_length_varint + maybe-compressed]

    where data_length is:
      - 0           if maybe-compressed is the raw uncompressed body
                    (used when len(body) < threshold)
      - body_size   if maybe-compressed is zlib(body)
                    (used when len(body) >= threshold)

The outer ``packet_length`` measures the bytes that follow the outer
varint (i.e., the inner header + data). The inner ``data_length`` is
the *uncompressed* body size, used by the receiver to validate
post-decompression sizing.
"""

from __future__ import annotations

import logging
import zlib

from minecraft_bot.codec import Writer, varint
from minecraft_bot.errors import DecodeError, OversizedVarInt

_log = logging.getLogger("minecraft_bot.protocol.framer")

# Hard cap on a single inbound packet's payload size. The protocol
# itself caps individual fields; this is a safety net against an
# oversized length prefix that would otherwise let us allocate
# unboundedly.
MAX_PACKET_SIZE = 2 * 1024 * 1024  # 2 MiB; ample for chunks (~1 MiB) plus headroom


class Framer:
    """Stateful packet framer over a single bidirectional stream.

    Use :meth:`feed` to push received bytes; call :meth:`try_extract`
    in a loop until it returns ``None`` to drain all complete packets
    from the internal buffer. Use :meth:`encode` to frame an outbound
    packet body for transmission.

    The :attr:`compression_threshold` is mutable so the connection
    layer can apply a server-issued ``Set Compression`` packet
    mid-session (FR-004). ``-1`` means compression is disabled
    entirely.
    """

    def __init__(self, *, compression_threshold: int = -1) -> None:
        self.compression_threshold: int = compression_threshold
        self._buf: bytearray = bytearray()

    # ----- inbound side ---------------------------------------------------

    def feed(self, data: bytes | bytearray | memoryview) -> None:
        """Push raw bytes from the socket into the internal buffer."""
        if data:
            self._buf.extend(data)

    def buffered_bytes(self) -> int:
        return len(self._buf)

    def try_extract(self) -> bytes | None:
        """Extract one complete packet body or return ``None``.

        The body returned is the byte sequence ``id_varint + payload``;
        the registry consumes it from there. Decompression (if any) is
        applied transparently.

        Raises :class:`DecodeError` for malformed frames (oversized
        varints, oversized packets, decompression failures, declared
        size mismatch).
        """
        if not self._buf:
            return None

        # 1) Outer packet length.
        length_result = _try_read_varint(bytes(self._buf))
        if length_result is None:
            # Insufficient bytes to determine length yet.
            return None
        packet_length, length_size = length_result
        if packet_length < 0:
            raise DecodeError(f"negative packet length: {packet_length}")
        if packet_length > MAX_PACKET_SIZE:
            raise DecodeError(
                f"packet length {packet_length} exceeds MAX_PACKET_SIZE ({MAX_PACKET_SIZE})"
            )

        total = length_size + packet_length
        if len(self._buf) < total:
            return None  # frame still incoming

        payload = bytes(self._buf[length_size:total])
        del self._buf[:total]

        # 2) Compression handling.
        if self.compression_threshold < 0:
            # Compression disabled; payload IS the body.
            return payload

        # Compression enabled — peel off the data-length varint.
        inner_result = _try_read_varint(payload)
        if inner_result is None:
            raise DecodeError("compressed frame missing inner data-length varint")
        data_length, inner_size = inner_result
        if data_length < 0:
            raise DecodeError(f"negative data_length: {data_length}")
        rest = payload[inner_size:]
        if data_length == 0:
            # Uncompressed body.
            return rest
        # Server SHOULD only compress bodies >= threshold. We tolerate but log.
        if data_length < self.compression_threshold:
            _log.warning(
                "received compressed frame with size %d below threshold %d",
                data_length, self.compression_threshold,
            )
        try:
            decompressed = zlib.decompress(rest)
        except zlib.error as exc:
            raise DecodeError(f"zlib decompress failed: {exc}") from exc
        if len(decompressed) != data_length:
            raise DecodeError(
                f"decompressed size {len(decompressed)} != declared {data_length}"
            )
        return decompressed

    # ----- outbound side --------------------------------------------------

    def encode(self, body: bytes) -> bytes:
        """Frame a packet body (``id_varint + payload``) for transmission."""
        if not isinstance(body, (bytes, bytearray)):
            raise TypeError("body must be bytes-like")
        if self.compression_threshold < 0:
            # No compression — just length-prefix.
            w = Writer(); varint.write(len(body), w)
            return w.bytes() + bytes(body)

        # Compression enabled.
        if len(body) >= self.compression_threshold:
            compressed = zlib.compress(bytes(body))
            inner_len_w = Writer(); varint.write(len(body), inner_len_w)
            inner = inner_len_w.bytes() + compressed
        else:
            inner_len_w = Writer(); varint.write(0, inner_len_w)
            inner = inner_len_w.bytes() + bytes(body)

        outer_w = Writer(); varint.write(len(inner), outer_w)
        return outer_w.bytes() + inner


def _try_read_varint(buf: bytes) -> tuple[int, int] | None:
    """Try to peel a VarInt off the front of ``buf``.

    Returns ``(value, bytes_consumed)`` if a complete varint is present,
    or ``None`` if more bytes are needed.

    Raises :class:`OversizedVarInt` if 5 bytes have been consumed and
    the continuation bit is still set (malformed input).
    """
    result = 0
    for i, b in enumerate(buf[:5]):
        result |= (b & 0x7F) << (7 * i)
        if (b & 0x80) == 0:
            # Sign-extend from bit 31.
            if result & (1 << 31):
                result -= 1 << 32
            return (result, i + 1)
    # Either ran out of bytes (need more) or the 5th byte still has continuation.
    if len(buf) < 5:
        return None
    raise OversizedVarInt(byte_count=6)


__all__ = ["MAX_PACKET_SIZE", "Framer"]
