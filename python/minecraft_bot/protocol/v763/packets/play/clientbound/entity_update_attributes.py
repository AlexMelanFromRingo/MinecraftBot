"""Packet `entity_update_attributes` (play/clientbound, id 0x6A).

Updates an entity's attribute set (max_health, movement_speed,
attack_damage, …). Each attribute has a base value and zero or more
modifiers (UUID-keyed adjustments).
"""

from __future__ import annotations

import struct
import uuid as _uuid_stdlib
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string, varint
from minecraft_bot.codec import uuid as uuid_codec

PACKET_ID = 0x6A


@dataclass(frozen=True, slots=True)
class AttributeModifier:
    uuid: _uuid_stdlib.UUID
    amount: float       # f64
    operation: int      # i8: 0=add, 1=multiply_base, 2=multiply_total


@dataclass(frozen=True, slots=True)
class AttributeProperty:
    name: str           # identifier (e.g., "minecraft:generic.movement_speed")
    value: float        # f64, base value
    modifiers: tuple[AttributeModifier, ...]


@dataclass(frozen=True, slots=True)
class EntityUpdateAttributes:
    entity_id: int
    properties: tuple[AttributeProperty, ...]


def decode(reader: Reader) -> EntityUpdateAttributes:
    eid = varint.read(reader)
    n_props = varint.read(reader)
    props: list[AttributeProperty] = []
    for _ in range(n_props):
        name = string.read(reader)
        val, = struct.unpack(">d", reader.read(8))
        n_mods = varint.read(reader)
        mods: list[AttributeModifier] = []
        for _ in range(n_mods):
            u = uuid_codec.read(reader)
            amt, = struct.unpack(">d", reader.read(8))
            op, = struct.unpack(">b", reader.read(1))
            mods.append(AttributeModifier(uuid=u, amount=amt, operation=op))
        props.append(AttributeProperty(name=name, value=val, modifiers=tuple(mods)))
    return EntityUpdateAttributes(entity_id=eid, properties=tuple(props))


def encode(packet: EntityUpdateAttributes, writer: Writer) -> None:
    varint.write(packet.entity_id, writer)
    varint.write(len(packet.properties), writer)
    for p in packet.properties:
        string.write(p.name, writer)
        writer.write(struct.pack(">d", p.value))
        varint.write(len(p.modifiers), writer)
        for m in p.modifiers:
            uuid_codec.write(m.uuid, writer)
            writer.write(struct.pack(">d", m.amount))
            writer.write(struct.pack(">b", m.operation))
