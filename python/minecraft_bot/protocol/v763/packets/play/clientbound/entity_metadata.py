"""Packet `entity_metadata` (play/clientbound, id 0x52).

Carries a stream of (index, type, value) entries describing an entity's
"data watcher" state (custom name, health, baby flag, item in slot,
pose, etc.). The stream is terminated by index ``0xFF``.

There are 24+ value-types in protocol 763 (byte, varint, varlong, float,
string, chat, opt_chat, slot, bool, rotation, position, opt_position,
direction, opt_uuid, block_state, opt_block_state, nbt, particle,
villager_data, opt_varint, pose, cat_variant, frog_variant,
opt_global_pos, painting_variant, sniffer_state, vec3f, quaternion).

Decoding the typed stream requires a per-type codec table. To keep this
file lean and to avoid bloat that would mostly serve niche bots, we
capture the **raw stream** as opaque bytes. Bot-API consumers that
need structured metadata access can parse the bytes via a separate
helper module.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x52


@dataclass(frozen=True, slots=True)
class EntityMetadata:
    entity_id: int
    metadata: bytes  # raw stream including the trailing 0xFF terminator


def decode(reader: Reader) -> EntityMetadata:
    eid = varint.read(reader)
    md = reader.read(reader.remaining())
    return EntityMetadata(entity_id=eid, metadata=md)


def encode(packet: EntityMetadata, writer: Writer) -> None:
    varint.write(packet.entity_id, writer)
    writer.write(packet.metadata)
