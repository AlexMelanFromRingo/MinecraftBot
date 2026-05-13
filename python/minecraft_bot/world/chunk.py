"""Chunk storage: PalettedContainer + ChunkSection + Chunk.

This is the data model that the structured ``map_chunk`` decoder
(:mod:`world.decode_chunk`) builds into; the World cache holds these
:class:`Chunk` instances keyed by ``(cx, cz)``.

Coordinate conventions
======================

- World coordinates are signed ints: ``x``, ``y``, ``z``.
- Chunk coordinates: ``cx = x >> 4``, ``cz = z >> 4``.
- Within a chunk: ``local_x = x & 15`` (0..15), ``local_z = z & 15``.
- Section index: ``section_idx = (y - min_y) >> 4``.
- Within a section: ``local_y = (y - min_y) & 15`` (0..15).

For overworld in 1.20.1: ``min_y = -64``, height = 384, so
``section_count = 24``.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class PalettedContainer:
    """Per-section paletted storage.

    Three modes (selected at decode time, exposed via fields):

    - **single-value mode**: every cell has the same value. ``palette
      is None``, ``data is None``, ``single_value`` set, ``bits == 0``.
    - **indexed mode**: ``palette`` is a list of values; ``data`` is a
      long-packed array of palette indices, ``bits_per_entry > 0``.
    - **direct mode**: ``palette is None``; ``data`` is a long-packed
      array of raw values, ``bits_per_entry`` is the direct-mode width.
    """

    bits_per_entry: int = 0
    palette: list[int] | None = None
    data: list[int] | None = None
    single_value: int | None = None

    def get(self, index: int) -> int:
        """Read the value at flat ``index`` (0..cells-1 for the
        container; the caller computes the linear index from x/y/z)."""
        if self.single_value is not None:
            return self.single_value
        assert self.data is not None, "non-single-value container missing data"
        entries_per_long = 64 // self.bits_per_entry
        long_idx = index // entries_per_long
        sub_idx = index % entries_per_long
        mask = (1 << self.bits_per_entry) - 1
        raw = (self.data[long_idx] >> (sub_idx * self.bits_per_entry)) & mask
        if self.palette is not None:
            if raw >= len(self.palette):
                # Corrupt or out-of-range index; return 0 (air-ish) instead of crashing.
                return 0
            return self.palette[raw]
        return raw

    def set(self, index: int, value: int) -> None:
        """Write the value at flat ``index``. May upgrade single-value
        mode to indexed mode if a different value is written."""
        if self.single_value is not None:
            if value == self.single_value:
                return
            # Promote to indexed mode. Bits = 4 minimum for block states.
            # For simplicity, jump straight to direct-mode-like indexed
            # with width 15 — caller pays the cost only on first mutation.
            self.bits_per_entry = 15
            n_cells = 4096   # 16x16x16
            entries_per_long = 64 // self.bits_per_entry
            n_longs = (n_cells + entries_per_long - 1) // entries_per_long
            # Fill with the old single_value packed across all entries.
            old = self.single_value
            self.palette = None
            mask = (1 << self.bits_per_entry) - 1
            self.data = []
            for _ in range(n_longs):
                packed = 0
                for slot in range(entries_per_long):
                    packed |= (old & mask) << (slot * self.bits_per_entry)
                self.data.append(packed)
            self.single_value = None

        assert self.data is not None
        entries_per_long = 64 // self.bits_per_entry
        long_idx = index // entries_per_long
        sub_idx = index % entries_per_long
        mask = (1 << self.bits_per_entry) - 1
        if self.palette is not None:
            # Indexed mode: find or append in palette.
            try:
                raw = self.palette.index(value)
            except ValueError:
                self.palette.append(value)
                raw = len(self.palette) - 1
                if raw > mask:
                    # Palette overflow — would need to widen. Promote
                    # to direct mode (rare; expensive).
                    self._promote_to_direct()
                    return self.set(index, value)
        else:
            raw = value
        # Clear then set.
        cleared = self.data[long_idx] & ~(mask << (sub_idx * self.bits_per_entry))
        self.data[long_idx] = cleared | ((raw & mask) << (sub_idx * self.bits_per_entry))

    def _promote_to_direct(self) -> None:
        """Convert indexed mode to direct mode (15 bits per entry)."""
        assert self.palette is not None and self.data is not None
        n_cells = 4096
        old_bits = self.bits_per_entry
        old_palette = self.palette
        old_data = self.data
        old_eppl = 64 // old_bits
        old_mask = (1 << old_bits) - 1
        values = []
        for i in range(n_cells):
            li = i // old_eppl
            si = i % old_eppl
            raw = (old_data[li] >> (si * old_bits)) & old_mask
            values.append(old_palette[raw] if raw < len(old_palette) else 0)
        # Re-pack at 15 bits.
        new_bits = 15
        new_eppl = 64 // new_bits
        new_mask = (1 << new_bits) - 1
        new_data = [0] * ((n_cells + new_eppl - 1) // new_eppl)
        for i, v in enumerate(values):
            li = i // new_eppl
            si = i % new_eppl
            new_data[li] |= (v & new_mask) << (si * new_bits)
        self.bits_per_entry = new_bits
        self.palette = None
        self.data = new_data


@dataclass(slots=True)
class ChunkSection:
    """16×16×16 paletted block-state + 4×4×4 paletted biome cells."""

    block_count: int = 0
    block_states: PalettedContainer = field(default_factory=PalettedContainer)
    biomes: PalettedContainer = field(default_factory=PalettedContainer)

    def get_block(self, lx: int, ly: int, lz: int) -> int:
        """Read block-state ID at local section coordinates (0..15)."""
        return self.block_states.get((ly << 8) | (lz << 4) | lx)

    def set_block(self, lx: int, ly: int, lz: int, state_id: int) -> None:
        self.block_states.set((ly << 8) | (lz << 4) | lx, state_id)


@dataclass(slots=True)
class BlockEntityRecord:
    """A block-entity (sign, chest, banner, ...) within a chunk."""

    x: int          # world coordinate
    y: int
    z: int
    type_id: int    # block-entity registry id
    nbt: object     # parsed NbtTag or None


@dataclass(slots=True)
class Chunk:
    """A 16×N×16 chunk."""

    cx: int
    cz: int
    sections: list[ChunkSection] = field(default_factory=list)
    block_entities: dict[tuple[int, int, int], BlockEntityRecord] = field(default_factory=dict)
    heightmaps: object = None  # parsed NbtTag of the heightmaps NBT
    min_y: int = -64  # overworld default
    section_count: int = 24

    def get_block(self, local_x: int, y: int, local_z: int) -> int:
        """Get block-state at chunk-local (lx, lz) and world ``y``."""
        section_idx = (y - self.min_y) >> 4
        if section_idx < 0 or section_idx >= len(self.sections):
            return 0  # outside loaded vertical range -> treat as air
        ly = (y - self.min_y) & 15
        return self.sections[section_idx].get_block(local_x, ly, local_z)

    def set_block(self, local_x: int, y: int, local_z: int, state_id: int) -> None:
        section_idx = (y - self.min_y) >> 4
        if section_idx < 0 or section_idx >= len(self.sections):
            return
        ly = (y - self.min_y) & 15
        self.sections[section_idx].set_block(local_x, ly, local_z, state_id)


__all__ = [
    "BlockEntityRecord",
    "Chunk",
    "ChunkSection",
    "PalettedContainer",
]
