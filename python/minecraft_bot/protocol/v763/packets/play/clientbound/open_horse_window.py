"""Packet `open_horse_window` (play/clientbound, id 0x20).

Opens a horse/donkey/llama inventory window. ``nb_slots`` tells the
client how many slots to render.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x20


@dataclass(frozen=True, slots=True)
class OpenHorseWindow:
    window_id: int   # u8
    nb_slots: int    # varint
    entity_id: int   # i32


def decode(reader: Reader) -> OpenHorseWindow:
    wid = reader.read(1)[0]
    n = varint.read(reader)
    eid, = struct.unpack(">i", reader.read(4))
    return OpenHorseWindow(window_id=wid, nb_slots=n, entity_id=eid)


def encode(packet: OpenHorseWindow, writer: Writer) -> None:
    writer.write(bytes([packet.window_id & 0xFF]))
    varint.write(packet.nb_slots, writer)
    writer.write(struct.pack(">i", packet.entity_id))
