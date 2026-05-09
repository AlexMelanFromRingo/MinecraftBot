"""Packet `name_item` (play/serverbound, id 0x23). Anvil rename input."""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string

PACKET_ID = 0x23


@dataclass(frozen=True, slots=True)
class NameItem:
    name: str


def decode(reader: Reader) -> NameItem:
    return NameItem(name=string.read(reader))


def encode(packet: NameItem, writer: Writer) -> None:
    string.write(packet.name, writer)
