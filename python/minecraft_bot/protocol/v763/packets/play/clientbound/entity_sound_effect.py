"""Packet `entity_sound_effect` (play/clientbound, id 0x61).

Plays a sound attached to a specific entity. Same sound-holder/category
shape as :class:`~minecraft_bot.protocol.v763.packets.play.clientbound.sound_effect.SoundEffect`,
plus an entity id.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Optional

from minecraft_bot.codec import Reader, Writer, string, varint
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x61


@dataclass(frozen=True, slots=True)
class EntitySoundEffect:
    sound_id: int                     # 0 = custom, 1+ = registry id
    custom_sound: Optional[str]
    custom_range: Optional[float]
    sound_category: int               # varint enum
    entity_id: int                    # varint
    volume: float                     # f32
    pitch: float                      # f32
    seed: int                         # i64


def decode(reader: Reader) -> EntitySoundEffect:
    sid = varint.read(reader)
    if sid == 0:
        cs: Optional[str] = string.read(reader)
        present = reader.read(1)[0]
        if present == 1:
            cr: Optional[float] = struct.unpack(">f", reader.read(4))[0]
        elif present == 0:
            cr = None
        else:
            raise ValueOutOfRange("entity_sound_effect.range.present", present)
    else:
        cs, cr = None, None
    cat = varint.read(reader)
    eid = varint.read(reader)
    vol, pitch = struct.unpack(">ff", reader.read(8))
    seed, = struct.unpack(">q", reader.read(8))
    return EntitySoundEffect(
        sound_id=sid, custom_sound=cs, custom_range=cr,
        sound_category=cat, entity_id=eid,
        volume=vol, pitch=pitch, seed=seed,
    )


def encode(packet: EntitySoundEffect, writer: Writer) -> None:
    varint.write(packet.sound_id, writer)
    if packet.sound_id == 0:
        if packet.custom_sound is None:
            raise ValueOutOfRange("entity_sound_effect.custom_sound", None)
        string.write(packet.custom_sound, writer)
        if packet.custom_range is None:
            writer.write(b"\x00")
        else:
            writer.write(b"\x01")
            writer.write(struct.pack(">f", packet.custom_range))
    varint.write(packet.sound_category, writer)
    varint.write(packet.entity_id, writer)
    writer.write(struct.pack(">ff", packet.volume, packet.pitch))
    writer.write(struct.pack(">q", packet.seed))
