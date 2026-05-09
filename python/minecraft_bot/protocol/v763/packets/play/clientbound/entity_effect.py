"""Packet `entity_effect` (play/clientbound, id 0x6C).

Applies a status effect (potion effect) to an entity.

``hide_particles`` is a packed flag byte per protocol::

    0x01  is_ambient (e.g. beacon)
    0x02  show_particles
    0x04  show_icon

Some 1.20+ servers send a ``factor_codec`` NBT (currently used for
dolphins-grace darkness fade); ``None`` when absent.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Optional

from minecraft_bot.codec import Reader, Writer, nbt, varint
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x6C


@dataclass(frozen=True, slots=True)
class EntityEffect:
    entity_id: int
    effect_id: int
    amplifier: int            # i8
    duration: int             # varint, ticks; -1 = infinite
    flags: int                # i8 bitfield
    factor_codec: Optional[nbt.NbtTag]


def decode(reader: Reader) -> EntityEffect:
    eid = varint.read(reader)
    effid = varint.read(reader)
    amp, = struct.unpack(">b", reader.read(1))
    dur = varint.read(reader)
    flags, = struct.unpack(">b", reader.read(1))
    present = reader.read(1)[0]
    if present == 1:
        fc: Optional[nbt.NbtTag] = nbt.read(reader)
    elif present == 0:
        fc = None
    else:
        raise ValueOutOfRange("entity_effect.factor_codec.present", present)
    return EntityEffect(entity_id=eid, effect_id=effid, amplifier=amp,
                        duration=dur, flags=flags, factor_codec=fc)


def encode(packet: EntityEffect, writer: Writer) -> None:
    varint.write(packet.entity_id, writer)
    varint.write(packet.effect_id, writer)
    writer.write(struct.pack(">b", packet.amplifier))
    varint.write(packet.duration, writer)
    writer.write(struct.pack(">b", packet.flags))
    if packet.factor_codec is None:
        writer.write(b"\x00")
    else:
        writer.write(b"\x01")
        nbt.write(packet.factor_codec, writer)
