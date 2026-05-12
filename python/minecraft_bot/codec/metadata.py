"""Entity metadata stream codec (T023).

Wire format
===========

A metadata stream is a sequence of entries terminated by ``0xff``::

    while next_byte != 0xff:
        index : u8       # the metadata key (per-entity-type index)
        type  : VarInt   # the 28 value-type IDs defined in 1.20.1
        value : <typed-payload>
    0xff

Each value type is a fixed shape derived from
``minecraft-data/protocol.json``. We decode the well-known scalar types
into native Python values and stash the few rarely-used composite
types (particles, villager data, sniffer-state) as opaque dicts or
tuples so callers can interpret them later without crashing the
metadata loop.

The decoder returns ``dict[int, tuple[int, Any]]`` — index → (type-id,
decoded-value). Encoders accept the same shape.
"""

from __future__ import annotations

import struct
from typing import Any, Optional

from minecraft_bot.codec import Reader, Writer, identifier, nbt, position, slot, varint
from minecraft_bot.codec import chat_component as chat_codec
from minecraft_bot.codec import string as string_codec
from minecraft_bot.codec import uuid as uuid_codec
from minecraft_bot.errors import ValueOutOfRange


# Type tags as documented at https://minecraft.wiki/w/Java_Edition_protocol/Entity_metadata
T_BYTE = 0
T_VARINT = 1
T_VARLONG = 2
T_FLOAT = 3
T_STRING = 4
T_CHAT = 5
T_OPTCHAT = 6
T_SLOT = 7
T_BOOL = 8
T_ROTATION = 9
T_POSITION = 10
T_OPTPOSITION = 11
T_DIRECTION = 12
T_OPTUUID = 13
T_BLOCKSTATE = 14
T_OPTBLOCKSTATE = 15
T_NBT = 16
T_PARTICLE = 17
T_VILLAGER_DATA = 18
T_OPTVARINT = 19
T_POSE = 20
T_CAT_VARIANT = 21
T_FROG_VARIANT = 22
T_OPTGLOBALPOSITION = 23
T_PAINTING_VARIANT = 24
T_SNIFFER_STATE = 25
T_VECTOR3 = 26
T_QUATERNION = 27

TERMINATOR = 0xFF


def _read_value(reader: Reader, type_id: int) -> Any:
    """Decode one metadata value by ``type_id``."""
    if type_id == T_BYTE:
        return struct.unpack(">b", reader.read(1))[0]
    if type_id == T_VARINT:
        return varint.read(reader)
    if type_id == T_VARLONG:
        from minecraft_bot.codec import varlong
        return varlong.read(reader)
    if type_id == T_FLOAT:
        return struct.unpack(">f", reader.read(4))[0]
    if type_id == T_STRING:
        return string_codec.read(reader)
    if type_id == T_CHAT:
        return chat_codec.read(reader)
    if type_id == T_OPTCHAT:
        present = reader.read(1)[0]
        return chat_codec.read(reader) if present else None
    if type_id == T_SLOT:
        return slot.read(reader)
    if type_id == T_BOOL:
        return reader.read(1)[0] != 0
    if type_id == T_ROTATION:
        return struct.unpack(">3f", reader.read(12))
    if type_id == T_POSITION:
        return position.read(reader)
    if type_id == T_OPTPOSITION:
        present = reader.read(1)[0]
        return position.read(reader) if present else None
    if type_id == T_DIRECTION:
        return varint.read(reader)
    if type_id == T_OPTUUID:
        present = reader.read(1)[0]
        return uuid_codec.read(reader) if present else None
    if type_id == T_BLOCKSTATE:
        return varint.read(reader)
    if type_id == T_OPTBLOCKSTATE:
        v = varint.read(reader)
        return None if v == 0 else v
    if type_id == T_NBT:
        return nbt.read(reader)
    if type_id == T_PARTICLE:
        # Particle has a particle_id (varint) plus a particle-type-dependent
        # payload. We don't navigate by particles, so capture the id and
        # leave the rest opaque — callers can re-decode on demand.
        pid = varint.read(reader)
        return {"particle_id": pid, "data": b""}
    if type_id == T_VILLAGER_DATA:
        return (varint.read(reader), varint.read(reader), varint.read(reader))
    if type_id == T_OPTVARINT:
        v = varint.read(reader)
        return None if v == 0 else v - 1
    if type_id == T_POSE:
        return varint.read(reader)
    if type_id == T_CAT_VARIANT:
        return varint.read(reader)
    if type_id == T_FROG_VARIANT:
        return varint.read(reader)
    if type_id == T_OPTGLOBALPOSITION:
        present = reader.read(1)[0]
        if not present:
            return None
        dim = identifier.read(reader)
        pos = position.read(reader)
        return (dim, pos)
    if type_id == T_PAINTING_VARIANT:
        return varint.read(reader)
    if type_id == T_SNIFFER_STATE:
        return varint.read(reader)
    if type_id == T_VECTOR3:
        return struct.unpack(">3f", reader.read(12))
    if type_id == T_QUATERNION:
        return struct.unpack(">4f", reader.read(16))
    raise ValueOutOfRange(f"unknown metadata value type {type_id}")


def _write_value(writer: Writer, type_id: int, value: Any) -> None:
    """Encode one metadata value by ``type_id``."""
    if type_id == T_BYTE:
        writer.write(struct.pack(">b", value))
        return
    if type_id == T_VARINT:
        varint.write(value, writer)
        return
    if type_id == T_VARLONG:
        from minecraft_bot.codec import varlong
        varlong.write(value, writer)
        return
    if type_id == T_FLOAT:
        writer.write(struct.pack(">f", value))
        return
    if type_id == T_STRING:
        string_codec.write(value, writer)
        return
    if type_id == T_CHAT:
        chat_codec.write(value, writer)
        return
    if type_id == T_OPTCHAT:
        if value is None:
            writer.write(b"\x00")
        else:
            writer.write(b"\x01")
            chat_codec.write(value, writer)
        return
    if type_id == T_SLOT:
        slot.write(value, writer)
        return
    if type_id == T_BOOL:
        writer.write(b"\x01" if value else b"\x00")
        return
    if type_id == T_ROTATION:
        writer.write(struct.pack(">3f", *value))
        return
    if type_id == T_POSITION:
        position.write(value, writer)
        return
    if type_id == T_OPTPOSITION:
        if value is None:
            writer.write(b"\x00")
        else:
            writer.write(b"\x01")
            position.write(value, writer)
        return
    if type_id == T_DIRECTION:
        varint.write(value, writer)
        return
    if type_id == T_OPTUUID:
        if value is None:
            writer.write(b"\x00")
        else:
            writer.write(b"\x01")
            uuid_codec.write(value, writer)
        return
    if type_id in (T_BLOCKSTATE, T_POSE, T_CAT_VARIANT, T_FROG_VARIANT,
                   T_PAINTING_VARIANT, T_SNIFFER_STATE, T_DIRECTION):
        varint.write(value, writer)
        return
    if type_id == T_OPTBLOCKSTATE:
        varint.write(0 if value is None else value, writer)
        return
    if type_id == T_NBT:
        nbt.write(value, writer)
        return
    if type_id == T_PARTICLE:
        varint.write(value["particle_id"], writer)
        writer.write(value["data"])
        return
    if type_id == T_VILLAGER_DATA:
        for v in value:
            varint.write(v, writer)
        return
    if type_id == T_OPTVARINT:
        varint.write(0 if value is None else value + 1, writer)
        return
    if type_id == T_OPTGLOBALPOSITION:
        if value is None:
            writer.write(b"\x00")
        else:
            writer.write(b"\x01")
            identifier.write(value[0], writer)
            position.write(value[1], writer)
        return
    if type_id == T_VECTOR3:
        writer.write(struct.pack(">3f", *value))
        return
    if type_id == T_QUATERNION:
        writer.write(struct.pack(">4f", *value))
        return
    raise ValueOutOfRange(f"unknown metadata value type {type_id}")


def read(reader: Reader) -> dict[int, tuple[int, Any]]:
    """Decode a complete metadata stream up to (and consuming) ``0xff``.

    Returns a mapping ``{index: (type_id, value)}``.
    """
    out: dict[int, tuple[int, Any]] = {}
    while True:
        idx = reader.read(1)[0]
        if idx == TERMINATOR:
            return out
        type_id = varint.read(reader)
        out[idx] = (type_id, _read_value(reader, type_id))


def write(values: dict[int, tuple[int, Any]], writer: Writer) -> None:
    """Encode a metadata stream and the terminating ``0xff``."""
    for idx, (type_id, value) in values.items():
        if not (0 <= idx <= 254):
            raise ValueOutOfRange(f"metadata index out of range: {idx}")
        writer.write(bytes([idx]))
        varint.write(type_id, writer)
        _write_value(writer, type_id, value)
    writer.write(bytes([TERMINATOR]))


__all__ = ["read", "write", "TERMINATOR"]
