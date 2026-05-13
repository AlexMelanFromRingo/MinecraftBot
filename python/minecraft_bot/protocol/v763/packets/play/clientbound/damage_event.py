"""Packet `damage_event` (play/clientbound, id 0x18).

Animation/sound trigger for an entity taking damage. The three "source"
fields are entity-ids referring to: type (the damage-type registry id),
cause (the entity that ultimately caused the damage, e.g., the shooter),
and direct (the entity that delivered the hit, e.g., the arrow).
``source_position`` may be present (e.g., for explosion damage).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x18


@dataclass(frozen=True, slots=True)
class DamageEvent:
    entity_id: int             # the entity that took damage
    source_type_id: int        # damage-type registry id
    source_cause_id: int       # entity id of the cause + 1 (0 = no cause)
    source_direct_id: int      # entity id of the direct dealer + 1 (0 = no direct)
    source_position: tuple[float, float, float] | None


def decode(reader: Reader) -> DamageEvent:
    eid = varint.read(reader)
    st = varint.read(reader)
    sc = varint.read(reader)
    sd = varint.read(reader)
    present = reader.read(1)[0]
    if present == 1:
        x, y, z = struct.unpack(">ddd", reader.read(24))
        sp: tuple[float, float, float] | None = (x, y, z)
    elif present == 0:
        sp = None
    else:
        raise ValueOutOfRange("damage_event.source_position.present", present)
    return DamageEvent(entity_id=eid, source_type_id=st, source_cause_id=sc,
                       source_direct_id=sd, source_position=sp)


def encode(packet: DamageEvent, writer: Writer) -> None:
    varint.write(packet.entity_id, writer)
    varint.write(packet.source_type_id, writer)
    varint.write(packet.source_cause_id, writer)
    varint.write(packet.source_direct_id, writer)
    if packet.source_position is None:
        writer.write(b"\x00")
    else:
        writer.write(b"\x01")
        x, y, z = packet.source_position
        writer.write(struct.pack(">ddd", x, y, z))
