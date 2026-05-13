"""Base entity hierarchy (T024).

The codegen tool (``tools/generate_entity_subclasses.py``) emits one
file per concrete entity type in
``python/minecraft_bot/entities/types/`` that subclasses one of these
six bases:

- :class:`Entity`         — root (positions, velocity, raw metadata dict,
                            indices 0..7 shared by every entity)
- :class:`LivingEntity`   — Entity + health, potion-effects, arrows-stuck,
                            absorption (indices 8..12 in 1.20.1)
- :class:`Mob`            — LivingEntity + AI flags
- :class:`Player`         — LivingEntity + score, skin parts, main hand
- :class:`ItemEntity`     — Entity + the held item slot
- :class:`Projectile`     — Entity (arrows, fireballs, snowballs, …)

Per-tracker code keeps these as **mutable** dataclasses (the entity
tracker mutates them in place as updates arrive). The metadata dict
is the source of truth; properties are thin readers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass(slots=True)
class Entity:
    """Root of the entity hierarchy.

    Mutable: the EntityTracker updates ``position`` / ``velocity`` /
    ``metadata`` as packets arrive.

    Shared metadata indices (1.20.1, present on every entity):

    - 0: byte flags (on fire, sneaking, sprinting, swimming, invisible,
         glowing, flying-with-elytra)
    - 1: varint air ticks (300 = max)
    - 2: optchat custom name
    - 3: bool custom name visible
    - 4: bool silent
    - 5: bool no gravity
    - 6: pose (varint)
    - 7: varint frozen ticks (powder snow)
    """

    eid: int
    uuid: UUID
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    yaw: float = 0.0
    pitch: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    on_ground: bool = False
    metadata: dict[int, tuple[int, Any]] = field(default_factory=dict)

    ENTITY_TYPE_ID: int = -1
    ENTITY_NAME: str = "entity"

    # --- shared accessors ------------------------------------------------

    def _md(self, idx: int) -> Any:
        entry = self.metadata.get(idx)
        return entry[1] if entry is not None else None

    @property
    def flags(self) -> int:
        """Byte bitmask — bit 0 on-fire, bit 1 sneaking, bit 3 sprinting,
        bit 4 swimming, bit 5 invisible, bit 6 glowing, bit 7 elytra-flying."""
        v = self._md(0)
        return v if v is not None else 0

    @property
    def is_on_fire(self) -> bool:    return bool(self.flags & 0x01)
    @property
    def is_sneaking(self) -> bool:   return bool(self.flags & 0x02)
    @property
    def is_sprinting(self) -> bool:  return bool(self.flags & 0x08)
    @property
    def is_swimming(self) -> bool:   return bool(self.flags & 0x10)
    @property
    def is_invisible(self) -> bool:  return bool(self.flags & 0x20)
    @property
    def is_glowing(self) -> bool:    return bool(self.flags & 0x40)
    @property
    def is_flying_elytra(self) -> bool: return bool(self.flags & 0x80)

    @property
    def air_ticks(self) -> int:
        v = self._md(1)
        return v if v is not None else 300

    @property
    def custom_name(self) -> Any | None:
        return self._md(2)

    @property
    def custom_name_visible(self) -> bool:
        return bool(self._md(3))

    @property
    def silent(self) -> bool:
        return bool(self._md(4))

    @property
    def no_gravity(self) -> bool:
        return bool(self._md(5))

    @property
    def pose(self) -> int:
        v = self._md(6)
        return v if v is not None else 0

    @property
    def frozen_ticks(self) -> int:
        v = self._md(7)
        return v if v is not None else 0

    @property
    def position(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)


@dataclass(slots=True)
class LivingEntity(Entity):
    """Anything with health / potion effects (animals, mobs, players).

    Adds indices 8..12 (1.20.1):

    - 8: varint hand state (bit 0 active-hand, bit 1 offhand, bit 2 riptide-spin)
    - 9: float health
    - 10: varint potion-effect colour (0 = none)
    - 11: bool potion-effect-is-ambient
    - 12: varint arrows-stuck
    - 13: varint bee-stinger-count
    - 14: optposition bed-sleeping-location
    """

    @property
    def hand_state(self) -> int:
        v = self._md(8)
        return v if v is not None else 0

    @property
    def health(self) -> float:
        v = self._md(9)
        return float(v) if v is not None else 0.0

    @property
    def is_alive(self) -> bool:
        return self.health > 0

    @property
    def potion_color(self) -> int:
        v = self._md(10)
        return v if v is not None else 0

    @property
    def arrows_stuck(self) -> int:
        v = self._md(12)
        return v if v is not None else 0

    @property
    def bee_stingers(self) -> int:
        v = self._md(13)
        return v if v is not None else 0


@dataclass(slots=True)
class Mob(LivingEntity):
    """Hostile / passive AI-driven mobs.

    Adds index 15: byte (bit 0 = no-AI, bit 1 = left-handed, bit 2 = aggressive)."""

    @property
    def mob_flags(self) -> int:
        v = self._md(15)
        return v if v is not None else 0

    @property
    def has_no_ai(self) -> bool:    return bool(self.mob_flags & 0x01)
    @property
    def is_left_handed(self) -> bool: return bool(self.mob_flags & 0x02)
    @property
    def is_aggressive(self) -> bool: return bool(self.mob_flags & 0x04)


@dataclass(slots=True)
class Player(LivingEntity):
    """Human players (other or our own).

    Adds 15..19:
    - 15: float absorption
    - 16: varint score
    - 17: byte skin-parts-bitmask
    - 18: byte main-hand (0 left, 1 right)
    - 19: NBT left-shoulder
    - 20: NBT right-shoulder
    """

    @property
    def absorption(self) -> float:
        v = self._md(15)
        return float(v) if v is not None else 0.0

    @property
    def score(self) -> int:
        v = self._md(16)
        return v if v is not None else 0

    @property
    def skin_parts(self) -> int:
        v = self._md(17)
        return v if v is not None else 0x7F  # default: all visible

    @property
    def main_hand(self) -> int:
        v = self._md(18)
        return v if v is not None else 1


@dataclass(slots=True)
class ItemEntity(Entity):
    """A dropped item floating in the world."""

    @property
    def item(self):
        return self._md(8)


@dataclass(slots=True)
class Projectile(Entity):
    """Arrows, fireballs, snowballs, eggs, ender-pearls, etc."""


__all__ = [
    "Entity",
    "ItemEntity",
    "LivingEntity",
    "Mob",
    "Player",
    "Projectile",
]
