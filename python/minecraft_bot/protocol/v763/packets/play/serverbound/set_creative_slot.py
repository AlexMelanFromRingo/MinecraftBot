"""Packet `set_creative_slot` (play/serverbound, id 0x2B).

Creative-mode only; lets the client place arbitrary item stacks
(including with NBT) into any inventory slot.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, slot

PACKET_ID = 0x2B


@dataclass(frozen=True, slots=True)
class SetCreativeSlot:
    slot_index: int  # i16
    item: slot.SlotData | None


def decode(reader: Reader) -> SetCreativeSlot:
    s, = struct.unpack(">h", reader.read(2))
    return SetCreativeSlot(slot_index=s, item=slot.read(reader))


def encode(packet: SetCreativeSlot, writer: Writer) -> None:
    writer.write(struct.pack(">h", packet.slot_index))
    slot.write(packet.item, writer)
