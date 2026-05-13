"""World cache (T030, FR-021..FR-024, FR-061..FR-067).

The :class:`World` is the bot's in-memory voxel cache. It is kept in
sync by subscribing to four clientbound packets:

- ``map_chunk``           — full chunk load (decoded into :class:`Chunk`)
- ``block_change``        — single-block update
- ``multi_block_change``  — batched section update
- ``unload_chunk``        — drop a chunk (server-driven eviction; the
                            World cache has no LRU per FR-024)

A ``respawn`` packet (dimension change) resets the entire cache via
:meth:`World.reset`.

The World implements the :class:`NavWorld` protocol expected by the
pathfinder (``is_solid`` / ``is_water`` / ``is_navigable_obstacle``).
"""

from __future__ import annotations

from collections.abc import Iterator

from minecraft_bot.world import block_table
from minecraft_bot.world.chunk import Chunk
from minecraft_bot.world.decode_chunk import decode as decode_chunk


class World:
    """The bot's voxel-world snapshot. Mutable; updated in place by
    Bot's clientbound packet handlers."""

    __slots__ = ("chunks", "dimension", "min_y", "section_count")

    def __init__(self, *, dimension: str = "minecraft:overworld",
                 min_y: int = -64, section_count: int = 24) -> None:
        self.chunks: dict[tuple[int, int], Chunk] = {}
        self.min_y = min_y
        self.section_count = section_count
        self.dimension = dimension

    # --- query ----------------------------------------------------------

    def get_chunk(self, cx: int, cz: int) -> Chunk | None:
        return self.chunks.get((cx, cz))

    def get_block(self, x: int, y: int, z: int) -> int:
        """Return the block-state ID at (x, y, z), or 0 (air) if the
        chunk is not loaded or y is out of range."""
        cx, cz = x >> 4, z >> 4
        chunk = self.chunks.get((cx, cz))
        if chunk is None:
            return 0
        return chunk.get_block(x & 0xF, y, z & 0xF)

    def get_block_name(self, x: int, y: int, z: int) -> str | None:
        return block_table.get_name(self.get_block(x, y, z))

    def is_solid(self, x: int, y: int, z: int) -> bool:
        return block_table.is_solid(self.get_block(x, y, z))

    def is_water(self, x: int, y: int, z: int) -> bool:
        return block_table.is_water(self.get_block(x, y, z))

    def is_navigable_obstacle(self, x: int, y: int, z: int) -> bool:
        return block_table.is_navigable_obstacle(self.get_block(x, y, z))

    # --- mutation by clientbound packets --------------------------------

    def apply_map_chunk(self, packet) -> Chunk:
        """Decode a ``map_chunk`` packet's payload and store the
        :class:`Chunk` in the cache. Returns the decoded chunk."""
        chunk = decode_chunk(
            packet.payload,
            cx=packet.chunk_x,
            cz=packet.chunk_z,
            min_y=self.min_y,
            section_count=self.section_count,
        )
        self.chunks[(chunk.cx, chunk.cz)] = chunk
        return chunk

    def apply_block_change(self, packet) -> None:
        """Apply a single-block update from a ``block_change`` packet."""
        x, y, z = packet.location
        cx, cz = x >> 4, z >> 4
        chunk = self.chunks.get((cx, cz))
        if chunk is None:
            return  # block in unloaded chunk — ignore (server didn't tell us)
        chunk.set_block(x & 0xF, y, z & 0xF, packet.block_state_id)

    def apply_multi_block_change(self, packet) -> None:
        """Apply a batched section update from ``multi_block_change``.

        Each record is a packed ``(state_id << 12) | rel_xyz`` where
        ``rel_xyz`` is ``(local_x << 8) | (local_z << 4) | local_y``.
        Section coords give the absolute world position of the section."""
        cx = packet.chunk_section_x
        cz = packet.chunk_section_z
        sy = packet.chunk_section_y
        chunk = self.chunks.get((cx, cz))
        if chunk is None:
            return
        section_base_y = sy * 16
        for rec in packet.records:
            state_id = rec >> 12
            rel = rec & 0xFFF
            lx = (rel >> 8) & 0xF
            lz = (rel >> 4) & 0xF
            ly = rel & 0xF
            world_y = section_base_y + ly
            chunk.set_block(lx, world_y, lz, state_id)

    def apply_unload_chunk(self, packet) -> None:
        """Drop a chunk that the server is unloading."""
        self.chunks.pop((packet.chunk_x, packet.chunk_z), None)

    def reset(self, *, dimension: str | None = None,
              min_y: int | None = None,
              section_count: int | None = None) -> None:
        """Wipe the cache (called on ``respawn`` / dimension change)."""
        self.chunks.clear()
        if dimension is not None:
            self.dimension = dimension
        if min_y is not None:
            self.min_y = min_y
        if section_count is not None:
            self.section_count = section_count

    # --- search (Phase 4 / US2 prep) -----------------------------------

    def find_blocks_nearby(
        self, name: str, origin: tuple[float, float, float], *,
        radius: int = 32, limit: int = 16,
    ) -> list[tuple[int, int, int]]:
        """Return up to ``limit`` block positions whose name == ``name``
        within Chebyshev radius ``radius`` of ``origin``, sorted
        ascending by squared Euclidean distance.

        ``name`` may be either the bare form (``"oak_log"``) or the
        ``minecraft:`` qualified form. Comparison is exact-match.
        """
        if ":" not in name:
            name = "minecraft:" + name
        ox, oy, oz = origin
        cx0, cz0 = int(ox) >> 4, int(oz) >> 4
        cr = (radius + 15) >> 4   # chunk radius (round up)
        matches: list[tuple[float, tuple[int, int, int]]] = []
        y_lo = max(int(oy - radius), self.min_y)
        y_hi = min(int(oy + radius) + 1, self.min_y + self.section_count * 16)
        for dcx in range(-cr, cr + 1):
            for dcz in range(-cr, cr + 1):
                chunk = self.chunks.get((cx0 + dcx, cz0 + dcz))
                if chunk is None:
                    continue
                base_x = (cx0 + dcx) * 16
                base_z = (cz0 + dcz) * 16
                for lx in range(16):
                    wx = base_x + lx
                    if abs(wx - ox) > radius:
                        continue
                    for lz in range(16):
                        wz = base_z + lz
                        if abs(wz - oz) > radius:
                            continue
                        for wy in range(y_lo, y_hi):
                            sid = chunk.get_block(lx, wy, lz)
                            if block_table.get_name(sid) == name:
                                dx, dy, dz = wx - ox, wy - oy, wz - oz
                                matches.append((dx * dx + dy * dy + dz * dz, (wx, wy, wz)))
        matches.sort(key=lambda m: m[0])
        return [pos for _, pos in matches[:limit]]

    def __iter__(self) -> Iterator[Chunk]:
        return iter(self.chunks.values())

    def __len__(self) -> int:
        return len(self.chunks)


__all__ = ["World"]
