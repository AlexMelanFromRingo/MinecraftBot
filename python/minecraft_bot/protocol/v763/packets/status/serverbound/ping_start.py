"""Packet `ping_start` (status/serverbound, id 0x00).

Triggers the server to send back a :class:`ServerInfo`. No payload.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x00


@dataclass(frozen=True, slots=True)
class PingStart:
    """Empty packet."""


def decode(reader: Reader) -> PingStart:
    return PingStart()


def encode(packet: PingStart, writer: Writer) -> None:
    pass
