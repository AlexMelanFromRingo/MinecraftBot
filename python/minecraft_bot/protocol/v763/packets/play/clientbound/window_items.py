"""Packet `window_items` (play/clientbound, id 0x12).

Full inventory snapshot for an open window. ``state_id`` increments on
each server-pushed change so the client can detect lost packets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from minecraft_bot.codec import Reader, Writer, slot, varint

PACKET_ID = 0x12


@dataclass(frozen=True, slots=True)
class WindowItems:
    window_id: int                # u8
    state_id: int                 # varint
    items: tuple[Optional[slot.SlotData], ...]
    carried_item: Optional[slot.SlotData]


def decode(reader: Reader) -> WindowItems:
    wid = reader.read(1)[0]
    state = varint.read(reader)
    n = varint.read(reader)
    items = tuple(slot.read(reader) for _ in range(n))
    carried = slot.read(reader)
    return WindowItems(window_id=wid, state_id=state, items=items, carried_item=carried)


def encode(packet: WindowItems, writer: Writer) -> None:
    writer.write(bytes([packet.window_id & 0xFF]))
    varint.write(packet.state_id, writer)
    varint.write(len(packet.items), writer)
    for it in packet.items:
        slot.write(it, writer)
    slot.write(packet.carried_item, writer)
