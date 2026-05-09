"""Packet `held_item_slot` (play/clientbound, id 0x4D).

Server tells the client which hotbar slot is currently selected.
``slot`` is 0..8.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x4D


@dataclass(frozen=True, slots=True)
class HeldItemSlot:
    slot: int  # i8


def decode(reader: Reader) -> HeldItemSlot:
    s, = struct.unpack(">b", reader.read(1))
    return HeldItemSlot(slot=s)


def encode(packet: HeldItemSlot, writer: Writer) -> None:
    writer.write(struct.pack(">b", packet.slot))
