"""Packet `face_player` (play/clientbound, id 0x3B).

Server tells the client to rotate the player's view to face a target
position or entity. ``feet_eyes`` is 0=feet, 1=eyes (anchor on the
caller). When ``is_entity`` is true, the packet carries an additional
entity id and target-anchor (``entity_feet_eyes``); otherwise the
target is the world position (x,y,z).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Optional

from minecraft_bot.codec import Reader, Writer, string, varint
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x3B


@dataclass(frozen=True, slots=True)
class FacePlayer:
    feet_eyes: int           # varint: 0=feet, 1=eyes
    x: float
    y: float
    z: float
    is_entity: bool
    entity_id: Optional[int]
    entity_feet_eyes: Optional[str]  # "feet" or "eyes" string


def decode(reader: Reader) -> FacePlayer:
    fe = varint.read(reader)
    x, y, z = struct.unpack(">ddd", reader.read(24))
    ie = reader.read(1)[0]
    if ie not in (0, 1):
        raise ValueOutOfRange("face_player.is_entity", ie)
    eid: Optional[int] = None
    efe: Optional[str] = None
    if ie == 1:
        eid = varint.read(reader)
        efe = string.read(reader)
    return FacePlayer(feet_eyes=fe, x=x, y=y, z=z, is_entity=ie == 1,
                      entity_id=eid, entity_feet_eyes=efe)


def encode(packet: FacePlayer, writer: Writer) -> None:
    varint.write(packet.feet_eyes, writer)
    writer.write(struct.pack(">ddd", packet.x, packet.y, packet.z))
    writer.write(b"\x01" if packet.is_entity else b"\x00")
    if packet.is_entity:
        if packet.entity_id is None or packet.entity_feet_eyes is None:
            raise ValueOutOfRange("face_player.entity_extras", packet.entity_id)
        varint.write(packet.entity_id, writer)
        string.write(packet.entity_feet_eyes, writer)
