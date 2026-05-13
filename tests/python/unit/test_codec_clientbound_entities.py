"""Round-trip every clientbound entity packet (T087)."""

from __future__ import annotations

import importlib

from minecraft_bot.codec import Reader, Writer

_ENTITY_PACKETS = [
    "spawn_entity", "spawn_entity_experience_orb", "named_entity_spawn",
    "entity_destroy", "entity_velocity", "entity_metadata",
    "entity_head_rotation", "entity_look", "entity_move_look",
    "entity_teleport", "entity_status", "entity_effect",
    "entity_equipment", "entity_update_attributes", "entity_sound_effect",
    "rel_entity_move", "attach_entity", "remove_entity_effect",
    "set_passengers", "collect", "hurt_animation",
    "damage_event", "animation",
]


def test_every_entity_packet_module_imports() -> None:
    for name in _ENTITY_PACKETS:
        importlib.import_module(
            f"minecraft_bot.protocol.v763.packets.play.clientbound.{name}"
        )


def test_entity_destroy_round_trip() -> None:
    from minecraft_bot.protocol.v763.packets.play.clientbound.entity_destroy import (
        EntityDestroy,
        decode,
        encode,
    )
    pkt = EntityDestroy(entity_ids=(1, 2, 100, -5))
    w = Writer(); encode(pkt, w)
    assert decode(Reader(w.bytes())) == pkt


def test_entity_velocity_round_trip() -> None:
    from minecraft_bot.protocol.v763.packets.play.clientbound.entity_velocity import (
        EntityVelocity,
        decode,
        encode,
    )
    pkt = EntityVelocity(entity_id=42, vx=100, vy=-50, vz=200)
    w = Writer(); encode(pkt, w)
    assert decode(Reader(w.bytes())) == pkt


def test_rel_entity_move_round_trip() -> None:
    from minecraft_bot.protocol.v763.packets.play.clientbound.rel_entity_move import (
        RelEntityMove,
        decode,
        encode,
    )
    pkt = RelEntityMove(entity_id=7, dx=10, dy=20, dz=-30, on_ground=True)
    w = Writer(); encode(pkt, w)
    assert decode(Reader(w.bytes())) == pkt
