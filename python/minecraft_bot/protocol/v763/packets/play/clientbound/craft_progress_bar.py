"""Packet `craft_progress_bar` (play/clientbound, id 0x13).

Updates a property of an open container (furnace fuel level, brewing
progress, enchantment seed, etc.). ``property`` and ``value`` semantics
depend on the container's window type.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x13


@dataclass(frozen=True, slots=True)
class CraftProgressBar:
    window_id: int   # u8
    property: int    # i16
    value: int       # i16


def decode(reader: Reader) -> CraftProgressBar:
    wid = reader.read(1)[0]
    prop, val = struct.unpack(">hh", reader.read(4))
    return CraftProgressBar(window_id=wid, property=prop, value=val)


def encode(packet: CraftProgressBar, writer: Writer) -> None:
    writer.write(bytes([packet.window_id & 0xFF]))
    writer.write(struct.pack(">hh", packet.property, packet.value))
