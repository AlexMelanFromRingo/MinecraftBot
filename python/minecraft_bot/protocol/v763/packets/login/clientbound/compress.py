"""Packet `compress` (login/clientbound, id 0x03).

Negotiates the zlib compression threshold for the connection.
``threshold == -1`` disables compression entirely; ``>= 0`` means
payloads of that size or larger are zlib-compressed (FR-004).
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x03


@dataclass(frozen=True, slots=True)
class Compress:
    threshold: int


def decode(reader: Reader) -> Compress:
    return Compress(threshold=varint.read(reader))


def encode(packet: Compress, writer: Writer) -> None:
    varint.write(packet.threshold, writer)
