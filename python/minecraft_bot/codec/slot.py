"""Slot codec — inventory item-stack data.

Wire format for protocol 763 (1.20.1)::

    bool present
    if present:
        VarInt item_id
        i8    count
        NBT   tag           # may be a single TAG_End byte for "no NBT"

Empty slot is encoded as a single ``0x00`` byte (``present = false``).

The Python side returns / accepts ``Optional[SlotData]`` — ``None``
means the slot is empty.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, nbt, varint
from minecraft_bot.errors import ValueOutOfRange


@dataclass(frozen=True, slots=True)
class SlotData:
    """A populated inventory slot."""

    item_id: int           # numeric item registry ID for the protocol version
    count: int             # i8; protocol allows -1..127, but typical range is 0..64
    tag: nbt.NbtTag | None = None  # item NBT, e.g. enchantments, custom name


def read(reader: Reader) -> SlotData | None:
    """Decode a slot. Returns ``None`` if the slot is empty (present=false)."""
    present = reader.read(1)[0]
    if present == 0:
        return None
    if present != 1:
        # The protocol only specifies 0 / 1; treat anything else as malformed.
        raise ValueOutOfRange("slot.present", present)
    item_id = varint.read(reader)
    (count,) = struct.unpack(">b", reader.read(1))
    tag = nbt.read(reader)
    return SlotData(item_id=item_id, count=count, tag=tag)


def write(value: SlotData | None, writer: Writer) -> None:
    """Encode a slot. ``None`` writes a single ``0x00`` byte."""
    if value is None:
        writer.write(b"\x00")
        return
    if not -128 <= value.count <= 127:
        raise ValueOutOfRange("slot.count", value.count)
    writer.write(b"\x01")
    varint.write(value.item_id, writer)
    writer.write(struct.pack(">b", value.count))
    nbt.write(value.tag, writer)


__all__ = ["SlotData", "read", "write"]
