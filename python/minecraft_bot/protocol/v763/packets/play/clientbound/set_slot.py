"""Packet `set_slot` (play/clientbound, id 0x14).

Updates a single inventory slot. ``window_id == 0`` is the player's
inventory; ``-1`` is the cursor (drag-and-drop preview); ``-2`` is the
"floating" item.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, slot, varint

PACKET_ID = 0x14


@dataclass(frozen=True, slots=True)
class SetSlot:
    window_id: int                # i8
    state_id: int                 # varint
    slot_index: int               # i16
    item: slot.SlotData | None


def decode(reader: Reader) -> SetSlot:
    wid, = struct.unpack(">b", reader.read(1))
    state = varint.read(reader)
    si, = struct.unpack(">h", reader.read(2))
    item = slot.read(reader)
    return SetSlot(window_id=wid, state_id=state, slot_index=si, item=item)


def encode(packet: SetSlot, writer: Writer) -> None:
    writer.write(struct.pack(">b", packet.window_id))
    varint.write(packet.state_id, writer)
    writer.write(struct.pack(">h", packet.slot_index))
    slot.write(packet.item, writer)
