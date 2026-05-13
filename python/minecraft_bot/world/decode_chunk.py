"""Structured decoder for the `map_chunk` packet payload.

In 001 the ``map_chunk`` packet's data was captured as opaque bytes
(see ``protocol/v763/packets/play/clientbound/map_chunk.py``). This
module decodes those bytes into a :class:`Chunk` so the World cache
can answer ``get_block(x, y, z)`` queries.

Wire format (1.20.1 / protocol 763), beginning *after* the
``(chunk_x, chunk_z)`` header that the packet's own decoder already
peels off:

  - heightmaps (NBT compound)
  - data: varint length + that many bytes (concatenation of section data)
  - block_entities: varint count + per-entity (packed xz byte + y short + type varint + NBT)
  - trust_edges: bool
  - sky_light_mask, block_light_mask, empty_sky_light_mask,
    empty_block_light_mask: each is a BitSet (varint long-count + longs)
  - sky_light: varint count + per-section (varint length + 2048 bytes)
  - block_light: varint count + per-section (varint length + 2048 bytes)

For Phase 2c we decode block-state sections + biomes + block-entities
+ heightmaps. Light data is kept as opaque bytes for now (the
pathfinder / physics don't need it; a future light-aware feature
will decode it).
"""

from __future__ import annotations

import struct

from minecraft_bot.codec import Reader as ByteReader
from minecraft_bot.codec import nbt as nbt_codec
from minecraft_bot.codec import varint as varint_codec
from minecraft_bot.world.chunk import (
    BlockEntityRecord,
    Chunk,
    ChunkSection,
    PalettedContainer,
)

# Per-section block-state paletted-container bit-widths.
#   bits == 0   -> single-value mode
#   1..4         -> normalised to 4 (vanilla minimum for blocks)
#   5..8         -> indexed
#   >= 9         -> direct (15 bits in protocol 763)
_BLOCK_MIN_INDEXED_BITS = 4
_BLOCK_MAX_INDEXED_BITS = 8
_BLOCK_DIRECT_BITS = 15
# Per-section biome paletted-container bit-widths.
_BIOME_MIN_INDEXED_BITS = 1
_BIOME_MAX_INDEXED_BITS = 3
_BIOME_DIRECT_BITS = 6


def _read_paletted(reader: ByteReader, *, is_block: bool) -> PalettedContainer:
    """Decode one paletted container (blocks or biomes)."""
    bits = reader.read(1)[0]
    if bits == 0:
        # Single-value mode: palette has one varint; data has 0 longs.
        value = varint_codec.read(reader)
        n_longs = varint_codec.read(reader)
        # Spec says 0 here; we tolerate non-zero and read them anyway.
        if n_longs > 0:
            reader.read(8 * n_longs)
        return PalettedContainer(bits_per_entry=0, single_value=value)

    if is_block:
        max_indexed = _BLOCK_MAX_INDEXED_BITS
        min_bits = _BLOCK_MIN_INDEXED_BITS
        direct_bits = _BLOCK_DIRECT_BITS
    else:
        max_indexed = _BIOME_MAX_INDEXED_BITS
        min_bits = _BIOME_MIN_INDEXED_BITS
        direct_bits = _BIOME_DIRECT_BITS

    if bits <= max_indexed:
        eff_bits = max(bits, min_bits)
        # Indexed mode: palette + long-packed data.
        palette_size = varint_codec.read(reader)
        palette = [varint_codec.read(reader) for _ in range(palette_size)]
        n_longs = varint_codec.read(reader)
        data = list(struct.unpack(f">{n_longs}q", reader.read(8 * n_longs))) if n_longs else []
        # Convert signed i64 to unsigned for bit math
        data = [d & 0xFFFFFFFFFFFFFFFF for d in data]
        return PalettedContainer(bits_per_entry=eff_bits, palette=palette, data=data)

    # Direct mode.
    n_longs = varint_codec.read(reader)
    data = list(struct.unpack(f">{n_longs}q", reader.read(8 * n_longs))) if n_longs else []
    data = [d & 0xFFFFFFFFFFFFFFFF for d in data]
    return PalettedContainer(bits_per_entry=direct_bits, palette=None, data=data)


def decode(
    payload: bytes,
    *,
    cx: int,
    cz: int,
    min_y: int = -64,
    section_count: int = 24,
) -> Chunk:
    """Decode the trailing payload of a ``map_chunk`` packet into a
    :class:`Chunk`. ``payload`` is the bytes after the
    ``(chunk_x, chunk_z)`` i32×2 header — i.e., the ``payload`` field
    of the v763 ``map_chunk`` dataclass.

    Parameters
    ----------
    payload : bytes
        Raw payload bytes.
    cx, cz : int
        Chunk coordinates (caller already decoded from the header).
    min_y : int, default -64
        Lower world Y for this dimension (overworld = -64; Nether = 0).
    section_count : int, default 24
        Number of 16-block vertical sections (overworld = 24).

    Returns
    -------
    Chunk
        Fully decoded chunk. Light data is **not** decoded by this
        milestone; it stays in the payload but is skipped.
    """
    reader = ByteReader(payload)

    # 1) Heightmaps NBT (network NBT — has root name in 1.20.1).
    heightmaps = nbt_codec.read(reader)

    # 2) Section data inside a length-prefixed buffer.
    data_len = varint_codec.read(reader)
    data_bytes = reader.read(data_len)
    sec_reader = ByteReader(data_bytes)
    sections: list[ChunkSection] = []
    for _ in range(section_count):
        # block_count (i16 BE), then block-state container, then biome container.
        block_count = struct.unpack(">h", sec_reader.read(2))[0]
        block_states = _read_paletted(sec_reader, is_block=True)
        biomes = _read_paletted(sec_reader, is_block=False)
        sections.append(
            ChunkSection(block_count=block_count, block_states=block_states, biomes=biomes)
        )

    # 3) Block entities array.
    n_be = varint_codec.read(reader)
    block_entities: dict[tuple[int, int, int], BlockEntityRecord] = {}
    base_x = cx * 16
    base_z = cz * 16
    for _ in range(n_be):
        packed_xz = reader.read(1)[0]
        lx = (packed_xz >> 4) & 0xF
        lz = packed_xz & 0xF
        y = struct.unpack(">h", reader.read(2))[0]
        type_id = varint_codec.read(reader)
        nbt_value = nbt_codec.read(reader)
        wx, wz = base_x + lx, base_z + lz
        block_entities[(wx, y, wz)] = BlockEntityRecord(
            x=wx, y=y, z=wz, type_id=type_id, nbt=nbt_value,
        )

    # Remaining bytes: trust_edges (bool) + 4 bitsets + 2 light arrays.
    # We don't decode these (Phase 2c scope); just drain the reader so
    # callers can assert no leftover.
    # (Drain only if the caller wants to assert; here we simply ignore.)

    return Chunk(
        cx=cx,
        cz=cz,
        sections=sections,
        block_entities=block_entities,
        heightmaps=heightmaps,
        min_y=min_y,
        section_count=section_count,
    )


__all__ = ["decode"]
