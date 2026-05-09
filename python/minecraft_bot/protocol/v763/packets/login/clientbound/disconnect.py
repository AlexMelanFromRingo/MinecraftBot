"""Packet `disconnect` (login/clientbound, id 0x00).

Server-initiated disconnect during the LOGIN state. ``reason`` is a
JSON-encoded chat component; the framework keeps it as a raw string
and surfaces it via :class:`~minecraft_bot.errors.KickedByServer`.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string

PACKET_ID = 0x00


@dataclass(frozen=True, slots=True)
class Disconnect:
    reason: str  # JSON chat component


def decode(reader: Reader) -> Disconnect:
    return Disconnect(reason=string.read(reader))


def encode(packet: Disconnect, writer: Writer) -> None:
    string.write(packet.reason, writer)
