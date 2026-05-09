"""Packet `enchant_item` (play/serverbound, id 0x0A)."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x0A


@dataclass(frozen=True, slots=True)
class EnchantItem:
    window_id: int   # i8
    enchantment: int # i8


def decode(reader: Reader) -> EnchantItem:
    wid, en = struct.unpack(">bb", reader.read(2))
    return EnchantItem(window_id=wid, enchantment=en)


def encode(packet: EnchantItem, writer: Writer) -> None:
    writer.write(struct.pack(">bb", packet.window_id, packet.enchantment))
