"""Packet `held_item_slot` (play/serverbound, id 0x28). Hotbar slot select."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x28


@dataclass(frozen=True, slots=True)
class HeldItemSlot:
    slot_id: int  # i16; 0..8


def decode(reader: Reader) -> HeldItemSlot:
    s, = struct.unpack(">h", reader.read(2))
    return HeldItemSlot(slot_id=s)


def encode(packet: HeldItemSlot, writer: Writer) -> None:
    writer.write(struct.pack(">h", packet.slot_id))
