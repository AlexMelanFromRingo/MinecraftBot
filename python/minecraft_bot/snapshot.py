"""BotSnapshot (T088).

A frozen, picklable view of the bot's full state at one instant.
Used by ML observation pipelines and replay tooling. Take a snapshot
with ``bot.snapshot()``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from minecraft_bot.entities.base import Entity
from minecraft_bot.inventory.item import ItemSlot
from minecraft_bot.status_effects import EffectEntry


@dataclass(frozen=True, slots=True)
class EntityRef:
    """Compact reference to an entity in a snapshot."""

    eid: int
    type_name: str
    x: float
    y: float
    z: float
    yaw: float
    pitch: float
    health: float = 0.0


@dataclass(frozen=True, slots=True)
class BotSnapshot:
    """A point-in-time picture of a bot's observable state.

    Equality + hash are dataclass defaults — snapshots are immutable
    and can be used as cache keys for replay-by-state pipelines.
    """

    # Kinematic
    x: float
    y: float
    z: float
    yaw: float
    pitch: float
    on_ground: bool

    # Vitals
    health: float
    food: int
    saturation: float
    is_dead: bool
    xp_level: int
    xp_total: int

    # Identity
    entity_id: Optional[int]
    game_mode: Optional[int]
    held_slot: int
    world_name: Optional[str]
    dimension: Optional[str]
    is_connected: bool

    # Aggregates (tuples for hashability)
    inventory: tuple[Optional[ItemSlot], ...] = field(default_factory=tuple)
    nearby_entities: tuple[EntityRef, ...] = field(default_factory=tuple)
    active_effects: tuple[EffectEntry, ...] = field(default_factory=tuple)


def make_snapshot(bot, *, nearby_radius: float = 32.0) -> BotSnapshot:
    """Construct a :class:`BotSnapshot` from the bot's current state."""
    nearby: list[EntityRef] = []
    for e in bot.nearby_entities(radius=nearby_radius):
        health = getattr(e, "health", 0.0)
        nearby.append(EntityRef(
            eid=e.eid,
            type_name=type(e).__name__,
            x=e.x, y=e.y, z=e.z,
            yaw=e.yaw, pitch=e.pitch,
            health=float(health) if health is not None else 0.0,
        ))
    return BotSnapshot(
        x=bot.x, y=bot.y, z=bot.z,
        yaw=bot.yaw, pitch=bot.pitch,
        on_ground=bot.on_ground,
        health=bot.health, food=bot.food, saturation=bot.saturation,
        is_dead=bot.is_dead,
        xp_level=bot.xp_level, xp_total=bot.xp_total,
        entity_id=bot.entity_id, game_mode=bot.game_mode,
        held_slot=bot.held_slot,
        world_name=bot.world_name, dimension=bot.dimension,
        is_connected=bot.is_connected,
        inventory=tuple(bot.inventory.items()),
        nearby_entities=tuple(nearby),
        active_effects=tuple(bot.effects.active_effects()),
    )


__all__ = ["BotSnapshot", "EntityRef", "make_snapshot"]
