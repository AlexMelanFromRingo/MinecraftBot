"""Chunk decode + paletted container tests (T018)."""

from __future__ import annotations

import struct

from minecraft_bot.world.chunk import (
    BlockEntityRecord,
    Chunk,
    ChunkSection,
    PalettedContainer,
)

# --- PalettedContainer modes -----------------------------------------------


def test_single_value_mode_get() -> None:
    pc = PalettedContainer(bits_per_entry=0, single_value=42)
    for i in (0, 100, 4095):
        assert pc.get(i) == 42


def test_single_value_mode_set_same_value_noop() -> None:
    pc = PalettedContainer(bits_per_entry=0, single_value=42)
    pc.set(100, 42)
    assert pc.single_value == 42
    assert pc.data is None


def test_single_value_mode_set_different_promotes_to_direct() -> None:
    pc = PalettedContainer(bits_per_entry=0, single_value=42)
    pc.set(100, 99)
    assert pc.single_value is None
    assert pc.bits_per_entry == 15
    assert pc.get(0) == 42  # other cells still 42
    assert pc.get(100) == 99
    assert pc.get(4095) == 42


def test_indexed_mode_round_trip() -> None:
    # Bits=4, 16 entries per long. 4096 cells = 256 longs.
    pc = PalettedContainer(
        bits_per_entry=4,
        palette=[0, 1, 5, 10],   # 4 entries (fits in 4 bits)
        data=[0] * 256,
    )
    pc.set(0, 5)
    pc.set(1, 10)
    pc.set(16, 5)
    assert pc.get(0) == 5
    assert pc.get(1) == 10
    assert pc.get(2) == 0  # unset, default 0 from palette
    assert pc.get(16) == 5


def test_indexed_mode_new_value_extends_palette() -> None:
    pc = PalettedContainer(
        bits_per_entry=4,
        palette=[0, 1, 5],
        data=[0] * 256,
    )
    pc.set(50, 99)  # 99 not in palette
    assert 99 in pc.palette
    assert pc.get(50) == 99


def test_direct_mode_get_set() -> None:
    # Bits=15, 4 entries per long. 4096 cells = 1024 longs.
    pc = PalettedContainer(
        bits_per_entry=15,
        palette=None,
        data=[0] * 1024,
    )
    pc.set(0, 12345)
    pc.set(4095, 32000)
    assert pc.get(0) == 12345
    assert pc.get(4095) == 32000
    assert pc.get(2048) == 0


# --- ChunkSection convenience wrappers ------------------------------------


def test_chunk_section_get_set_local_coords() -> None:
    sec = ChunkSection(
        block_count=0,
        block_states=PalettedContainer(bits_per_entry=15, data=[0] * 1024),
        biomes=PalettedContainer(bits_per_entry=0, single_value=1),
    )
    sec.set_block(3, 7, 11, 42)
    assert sec.get_block(3, 7, 11) == 42
    assert sec.get_block(0, 0, 0) == 0


# --- Chunk vertical addressing -------------------------------------------


def test_chunk_get_block_negative_y() -> None:
    """Chunk with min_y = -64 should handle y = -60 correctly."""
    chunk = Chunk(
        cx=0, cz=0, min_y=-64, section_count=24,
        sections=[
            ChunkSection(
                block_count=0,
                block_states=PalettedContainer(bits_per_entry=0, single_value=i),
                biomes=PalettedContainer(bits_per_entry=0, single_value=0),
            )
            for i in range(24)
        ],
    )
    # y = -64..-49 -> section 0 (single_value 0)
    assert chunk.get_block(0, -60, 0) == 0
    # y = -48..-33 -> section 1 (single_value 1)
    assert chunk.get_block(0, -48, 0) == 1
    # y = 64 -> section 8 ((64 - -64) >> 4 = 8)
    assert chunk.get_block(0, 64, 0) == 8


def test_chunk_get_block_outside_vertical_range_returns_zero() -> None:
    chunk = Chunk(cx=0, cz=0, min_y=-64, sections=[])
    assert chunk.get_block(0, 100, 0) == 0


# --- Block entities ------------------------------------------------------


def test_block_entity_record_keyed_by_world_pos() -> None:
    chunk = Chunk(
        cx=2, cz=3, min_y=-64,
        block_entities={
            (32, 64, 48): BlockEntityRecord(x=32, y=64, z=48, type_id=7, nbt=None)
        },
    )
    assert (32, 64, 48) in chunk.block_entities
    rec = chunk.block_entities[(32, 64, 48)]
    assert rec.type_id == 7


# --- End-to-end decode of a synthetic minimal chunk ----------------------


def test_decode_minimal_chunk() -> None:
    """Build a minimal payload and decode it; assert structure."""
    from minecraft_bot.codec import Writer, nbt, varint

    # Heightmaps: empty NBT compound.
    w = Writer()
    nbt.write(nbt.NbtCompound(), w)

    # Sections data: 24 sections, each with single-value air (state 0).
    sec_w = Writer()
    for _ in range(24):
        sec_w.write(struct.pack(">h", 0))  # block_count = 0
        # Block states paletted container: bits=0 (single-value), value=0, data=0 longs.
        sec_w.write(b"\x00")
        varint.write(0, sec_w)  # single value
        varint.write(0, sec_w)  # n_longs
        # Biomes paletted container: bits=0, single value=1, data=0 longs.
        sec_w.write(b"\x00")
        varint.write(1, sec_w)
        varint.write(0, sec_w)
    sec_bytes = sec_w.bytes()
    varint.write(len(sec_bytes), w)
    w.write(sec_bytes)

    # Block entities: zero.
    varint.write(0, w)

    payload = w.bytes()

    from minecraft_bot.world.decode_chunk import decode
    chunk = decode(payload, cx=5, cz=-3, min_y=-64, section_count=24)
    assert chunk.cx == 5
    assert chunk.cz == -3
    assert len(chunk.sections) == 24
    # Every block in every section should be air (state 0).
    for sec in chunk.sections:
        assert sec.get_block(0, 0, 0) == 0
        assert sec.get_block(15, 15, 15) == 0
    # No block entities.
    assert chunk.block_entities == {}
