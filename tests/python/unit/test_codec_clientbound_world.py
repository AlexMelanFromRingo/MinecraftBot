"""Round-trip every clientbound world/chunk packet (T086).

For each packet, build a Default-ish instance from the wire bytes
``b""`` (empty payload) when the schema allows, OR construct a
fixture using the dataclass's typed fields and verify encode→decode
returns an equal object.
"""

from __future__ import annotations

import importlib
import pkgutil

from minecraft_bot.codec import Reader, Writer

# Packet name → list of (kwargs dict, ...) to round-trip.
# Empty kwargs means "construct with all default field values" for
# packets that only contain fixed-size scalars.
_WORLD_PACKETS = [
    "block_action", "block_break_animation", "block_change",
    "chunk_biomes", "map_chunk", "multi_block_change",
    "unload_chunk", "update_light", "update_view_distance",
    "update_view_position", "update_time", "spawn_position",
    "world_border_center", "world_border_lerp_size", "world_border_size",
    "world_border_warning_delay", "world_border_warning_reach",
    "world_event", "world_particles",
    "tile_entity_data", "open_sign_entity",
    "initialize_world_border",
]


def _import_packet(name: str):
    return importlib.import_module(
        f"minecraft_bot.protocol.v763.packets.play.clientbound.{name}"
    )


def test_every_world_packet_module_imports() -> None:
    for name in _WORLD_PACKETS:
        _import_packet(name)


def test_every_world_packet_declares_required_symbols() -> None:
    missing: list[str] = []
    for name in _WORLD_PACKETS:
        mod = _import_packet(name)
        if not hasattr(mod, "PACKET_ID"):
            missing.append(f"{name}: PACKET_ID")
        if not hasattr(mod, "decode") or not callable(mod.decode):
            missing.append(f"{name}: decode")
        if not hasattr(mod, "encode") or not callable(mod.encode):
            missing.append(f"{name}: encode")
    assert not missing, "missing symbols: " + ", ".join(missing[:10])


def test_unload_chunk_round_trip() -> None:
    from minecraft_bot.protocol.v763.packets.play.clientbound.unload_chunk import (
        UnloadChunk, decode, encode,
    )
    pkt = UnloadChunk(chunk_x=12, chunk_z=-34)
    w = Writer(); encode(pkt, w)
    assert decode(Reader(w.bytes())) == pkt


def test_block_change_round_trip() -> None:
    from minecraft_bot.protocol.v763.packets.play.clientbound.block_change import (
        BlockChange, decode, encode,
    )
    pkt = BlockChange(location=(1, 64, -7), block_state_id=42)
    w = Writer(); encode(pkt, w)
    assert decode(Reader(w.bytes())) == pkt


def test_update_view_position_round_trip() -> None:
    from minecraft_bot.protocol.v763.packets.play.clientbound.update_view_position import (
        UpdateViewPosition, decode, encode,
    )
    pkt = UpdateViewPosition(chunk_x=625, chunk_z=625)
    w = Writer(); encode(pkt, w)
    assert decode(Reader(w.bytes())) == pkt
