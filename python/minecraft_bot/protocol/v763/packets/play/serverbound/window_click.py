"""Packet `window_click` (play/serverbound, id 0x0B).

Inventory click. ``mode`` codes: 0=normal, 1=shift-click, 2=hotbar swap,
3=middle-click, 4=drop, 5=drag, 6=double-click. ``changed_slots`` is a
list of (slot_index, new_item) tuples reflecting the client's
optimistic prediction.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, slot, varint

PACKET_ID = 0x0B


@dataclass(frozen=True, slots=True)
class ChangedSlot:
    slot_index: int                 # i16
    item: slot.SlotData | None


@dataclass(frozen=True, slots=True)
class WindowClick:
    window_id: int                  # u8
    state_id: int                   # varint
    slot_index: int                 # i16
    mouse_button: int               # i8
    mode: int                       # varint
    changed_slots: tuple[ChangedSlot, ...]
    carried_item: slot.SlotData | None


def decode(reader: Reader) -> WindowClick:
    wid = reader.read(1)[0]
    state = varint.read(reader)
    si, = struct.unpack(">h", reader.read(2))
    mb, = struct.unpack(">b", reader.read(1))
    mode = varint.read(reader)
    n = varint.read(reader)
    changed: list[ChangedSlot] = []
    for _ in range(n):
        s, = struct.unpack(">h", reader.read(2))
        item = slot.read(reader)
        changed.append(ChangedSlot(slot_index=s, item=item))
    carried = slot.read(reader)
    return WindowClick(
        window_id=wid, state_id=state, slot_index=si,
        mouse_button=mb, mode=mode,
        changed_slots=tuple(changed), carried_item=carried,
    )


def encode(packet: WindowClick, writer: Writer) -> None:
    writer.write(bytes([packet.window_id & 0xFF]))
    varint.write(packet.state_id, writer)
    writer.write(struct.pack(">h", packet.slot_index))
    writer.write(struct.pack(">b", packet.mouse_button))
    varint.write(packet.mode, writer)
    varint.write(len(packet.changed_slots), writer)
    for cs in packet.changed_slots:
        writer.write(struct.pack(">h", cs.slot_index))
        slot.write(cs.item, writer)
    slot.write(packet.carried_item, writer)
