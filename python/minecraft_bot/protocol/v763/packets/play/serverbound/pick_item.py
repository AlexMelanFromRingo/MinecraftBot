"""Packet `pick_item` (play/serverbound, id 0x1A). Creative middle-click."""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x1A


@dataclass(frozen=True, slots=True)
class PickItem:
    slot: int  # varint, source inventory slot to copy


def decode(reader: Reader) -> PickItem:
    return PickItem(slot=varint.read(reader))


def encode(packet: PickItem, writer: Writer) -> None:
    varint.write(packet.slot, writer)
