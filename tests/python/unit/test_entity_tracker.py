"""EntityTracker spawn/move/destroy/metadata lifecycle (T049)."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from uuid import UUID, uuid4

from minecraft_bot.codec import Writer
from minecraft_bot.codec import metadata as md
from minecraft_bot.entities.base import Entity, Player
from minecraft_bot.entities.tracker import EntityTracker
from minecraft_bot.entities.types import lookup_class
from minecraft_bot.protocol.v763.packets.play.clientbound.entity_destroy import (
    EntityDestroy,
)
from minecraft_bot.protocol.v763.packets.play.clientbound.entity_metadata import (
    EntityMetadata,
)
from minecraft_bot.protocol.v763.packets.play.clientbound.entity_move_look import (
    EntityMoveLook,
)
from minecraft_bot.protocol.v763.packets.play.clientbound.entity_teleport import (
    EntityTeleport,
)
from minecraft_bot.protocol.v763.packets.play.clientbound.entity_velocity import (
    EntityVelocity,
)
from minecraft_bot.protocol.v763.packets.play.clientbound.named_entity_spawn import (
    NamedEntitySpawn,
)
from minecraft_bot.protocol.v763.packets.play.clientbound.rel_entity_move import (
    RelEntityMove,
)
from minecraft_bot.protocol.v763.packets.play.clientbound.spawn_entity import (
    SpawnEntity,
)


def _spawn(type_id: int, eid: int = 42, **kw) -> SpawnEntity:
    defaults = dict(
        entity_id=eid, object_uuid=uuid4(), entity_type=type_id,
        x=10.0, y=64.0, z=20.0, pitch=0, yaw=0, head_pitch=0,
        object_data=0, vx=0, vy=0, vz=0,
    )
    defaults.update(kw)
    return SpawnEntity(**defaults)


def test_spawn_entity_creates_typed_subclass() -> None:
    """Sheep (type 82) spawn → tracker holds a Sheep instance."""
    tracker = EntityTracker()
    sheep_cls = lookup_class(82)
    assert sheep_cls.__name__ == "Sheep"
    tracker.on_spawn_entity(_spawn(type_id=82, eid=42))
    e = tracker.find_by_id(42)
    assert e is not None
    assert isinstance(e, sheep_cls)
    assert e.x == 10.0


def test_named_entity_spawn_creates_player() -> None:
    tracker = EntityTracker()
    pkt = NamedEntitySpawn(
        entity_id=99, player_uuid=uuid4(),
        x=5.0, y=64.0, z=-5.0, yaw=0, pitch=0,
    )
    tracker.on_named_entity_spawn(pkt)
    e = tracker.find_by_id(99)
    assert e is not None
    assert isinstance(e, Player)


def test_rel_entity_move_updates_position() -> None:
    tracker = EntityTracker()
    tracker.on_spawn_entity(_spawn(type_id=82, eid=42))
    # rel_entity_move: dx = 4096 → +1.0 block
    tracker.on_rel_entity_move(RelEntityMove(
        entity_id=42, dx=4096, dy=0, dz=0, on_ground=True,
    ))
    e = tracker.find_by_id(42)
    assert e.x == 11.0
    assert e.on_ground is True


def test_entity_teleport_overrides_position() -> None:
    tracker = EntityTracker()
    tracker.on_spawn_entity(_spawn(type_id=82, eid=42))
    tracker.on_entity_teleport(EntityTeleport(
        entity_id=42, x=100.5, y=64.0, z=200.5, yaw=64, pitch=-32, on_ground=False,
    ))
    e = tracker.find_by_id(42)
    assert e.x == 100.5
    assert e.z == 200.5
    assert e.on_ground is False
    assert e.yaw == 64 * (360.0 / 256.0)


def test_entity_velocity_normalises_to_blocks_per_tick() -> None:
    tracker = EntityTracker()
    tracker.on_spawn_entity(_spawn(type_id=82, eid=42))
    # vx = 8000 → 1.0 block/tick
    tracker.on_entity_velocity(EntityVelocity(entity_id=42, vx=8000, vy=0, vz=-8000))
    e = tracker.find_by_id(42)
    assert e.vx == 1.0
    assert e.vz == -1.0


def test_entity_metadata_merge_into_dict() -> None:
    tracker = EntityTracker()
    tracker.on_spawn_entity(_spawn(type_id=82, eid=42))
    # Build a metadata stream with index 0 = byte 0x10 (sprinting flag)
    w = Writer()
    md.write({0: (md.T_BYTE, 0x10)}, w)
    tracker.on_entity_metadata(EntityMetadata(entity_id=42, metadata=w.bytes()))
    e = tracker.find_by_id(42)
    assert e.metadata[0] == (md.T_BYTE, 0x10)
    # And the typed accessor on Entity should read sprinting=True now.
    assert e.is_sprinting is False  # wait, flag bit for sprint is 0x08, not 0x10
    # 0x10 is swimming
    assert e.is_swimming is True


def test_entity_destroy_removes_entities() -> None:
    tracker = EntityTracker()
    tracker.on_spawn_entity(_spawn(type_id=82, eid=42))
    tracker.on_spawn_entity(_spawn(type_id=82, eid=43))
    assert len(tracker) == 2
    tracker.on_entity_destroy(EntityDestroy(entity_ids=(42,)))
    assert len(tracker) == 1
    assert tracker.find_by_id(42) is None


def test_nearby_entities_filters_by_radius_and_excludes_bot() -> None:
    tracker = EntityTracker()
    tracker.bot_eid = 999
    # Bot itself
    tracker.on_spawn_entity(_spawn(type_id=82, eid=999, x=0.0, y=0.0, z=0.0))
    # 5 blocks away
    tracker.on_spawn_entity(_spawn(type_id=82, eid=1, x=5.0, y=0.0, z=0.0))
    # 20 blocks away
    tracker.on_spawn_entity(_spawn(type_id=82, eid=2, x=20.0, y=0.0, z=0.0))
    near = tracker.nearby_entities((0.0, 0.0, 0.0), radius=10.0)
    eids = [e.eid for e in near]
    assert 999 not in eids
    assert 1 in eids
    assert 2 not in eids


def test_nearby_entities_sorted_by_distance() -> None:
    tracker = EntityTracker()
    tracker.on_spawn_entity(_spawn(type_id=82, eid=1, x=8.0, y=0.0, z=0.0))
    tracker.on_spawn_entity(_spawn(type_id=82, eid=2, x=3.0, y=0.0, z=0.0))
    tracker.on_spawn_entity(_spawn(type_id=82, eid=3, x=5.0, y=0.0, z=0.0))
    near = tracker.nearby_entities((0.0, 0.0, 0.0), radius=20.0)
    assert [e.eid for e in near] == [2, 3, 1]


def test_type_filter_returns_only_players() -> None:
    tracker = EntityTracker()
    # Add sheep + player at same position
    tracker.on_spawn_entity(_spawn(type_id=82, eid=1, x=1.0, y=0.0, z=0.0))
    tracker.on_named_entity_spawn(NamedEntitySpawn(
        entity_id=2, player_uuid=uuid4(),
        x=1.0, y=0.0, z=0.0, yaw=0, pitch=0,
    ))
    players = tracker.nearby_players((0.0, 0.0, 0.0), radius=10.0)
    assert len(players) == 1
    assert players[0].eid == 2


def test_unknown_packet_silent_when_entity_missing() -> None:
    tracker = EntityTracker()
    # Update for non-existent entity should be silent no-op.
    tracker.on_rel_entity_move(RelEntityMove(
        entity_id=12345, dx=100, dy=0, dz=0, on_ground=True,
    ))
    assert tracker.find_by_id(12345) is None
