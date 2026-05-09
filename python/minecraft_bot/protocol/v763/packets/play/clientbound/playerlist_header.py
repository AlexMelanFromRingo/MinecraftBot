"""Packet `playerlist_header` (play/clientbound, id 0x65).

Tab-list header and footer text (both JSON chat components).
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string

PACKET_ID = 0x65


@dataclass(frozen=True, slots=True)
class PlayerlistHeader:
    header: str  # JSON chat component
    footer: str  # JSON chat component


def decode(reader: Reader) -> PlayerlistHeader:
    h = string.read(reader)
    f = string.read(reader)
    return PlayerlistHeader(header=h, footer=f)


def encode(packet: PlayerlistHeader, writer: Writer) -> None:
    string.write(packet.header, writer)
    string.write(packet.footer, writer)
