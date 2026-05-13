"""EntityTracker (T045).

Maintains a snapshot of all entities the server has told us about,
keyed by ``entity_id``. The :class:`Bot` owns one tracker and uses
it for :meth:`Bot.nearby_entities`, :meth:`Bot.attack`, follow,
auto-aim etc.

Subscribes to:

- ``spawn_entity`` / ``spawn_entity_experience_orb`` — non-player entities
- ``named_entity_spawn``                            — players
- ``entity_metadata``                                — typed metadata stream
- ``rel_entity_move`` / ``entity_move_look``         — delta position
- ``entity_teleport``                                — absolute position
- ``entity_look``                                    — rotation only
- ``entity_velocity``                                — momentum
- ``entity_head_rotation``                           — head yaw
- ``entity_destroy``                                 — remove
"""

from __future__ import annotations

import math
from collections.abc import Iterable

from minecraft_bot.codec import Reader as _Reader
from minecraft_bot.codec import metadata as _metadata
from minecraft_bot.entities.base import Entity, Player
from minecraft_bot.entities.types import LOOKUP, lookup_class

# Resolve the runtime Player subclass from the codegen lookup at import
# time. If for some reason it's missing (modded server with no Player
# in the registry), fall back to the abstract base Player.
_PLAYER_CLS = LOOKUP.get(122, Player)

# Fixed-point conversion constants.
_REL_MOVE_DIV = 4096.0        # rel_entity_move uses 1/4096 block units
_VELOCITY_DIV = 8000.0        # entity_velocity uses 1/8000 block/tick
_ANGLE_FROM_BYTE = 360.0 / 256.0   # i8 → degrees


class EntityTracker:
    """Indexed mutable snapshot of every entity the server has spawned
    for this client.

    Stored entities are *mutable* dataclass instances — the tracker
    updates fields in place as packets arrive.
    """

    __slots__ = ("_entities", "bot_eid")

    def __init__(self) -> None:
        self._entities: dict[int, Entity] = {}
        self.bot_eid: int | None = None

    # --- access ---------------------------------------------------------

    def __len__(self) -> int:
        return len(self._entities)

    def __iter__(self) -> Iterable[Entity]:
        return iter(self._entities.values())

    def __contains__(self, eid: int) -> bool:
        return eid in self._entities

    def find_by_id(self, eid: int) -> Entity | None:
        return self._entities.get(eid)

    def all(self) -> list[Entity]:
        return list(self._entities.values())

    def nearby_entities(
        self,
        origin: tuple[float, float, float],
        *,
        radius: float = 32.0,
        type_filter: type | None = None,
    ) -> list[Entity]:
        """Return entities within ``radius`` of ``origin``, sorted ascending
        by distance. ``type_filter`` matches against ``isinstance``."""
        ox, oy, oz = origin
        r2 = radius * radius
        out: list[tuple[float, Entity]] = []
        for ent in self._entities.values():
            if ent.eid == self.bot_eid:
                continue
            if type_filter is not None and not isinstance(ent, type_filter):
                continue
            dx, dy, dz = ent.x - ox, ent.y - oy, ent.z - oz
            d2 = dx * dx + dy * dy + dz * dz
            if d2 <= r2:
                out.append((d2, ent))
        out.sort(key=lambda p: p[0])
        return [e for _, e in out]

    def nearby_players(
        self, origin: tuple[float, float, float], *, radius: float = 32.0,
    ) -> list[Player]:
        return [e for e in self.nearby_entities(origin, radius=radius, type_filter=Player)]

    def distance_to(self, eid: int, origin: tuple[float, float, float]) -> float | None:
        e = self._entities.get(eid)
        if e is None:
            return None
        dx, dy, dz = e.x - origin[0], e.y - origin[1], e.z - origin[2]
        return math.sqrt(dx * dx + dy * dy + dz * dz)

    # --- packet handlers -----------------------------------------------

    def on_spawn_entity(self, p) -> Entity:
        """Generic non-player spawn (spawn_entity packet)."""
        cls = lookup_class(p.entity_type)
        ent = cls(
            eid=p.entity_id,
            uuid=p.object_uuid,
            x=p.x, y=p.y, z=p.z,
            yaw=p.yaw * _ANGLE_FROM_BYTE,
            pitch=p.pitch * _ANGLE_FROM_BYTE,
            vx=p.vx / _VELOCITY_DIV,
            vy=p.vy / _VELOCITY_DIV,
            vz=p.vz / _VELOCITY_DIV,
            on_ground=False,
        )
        self._entities[p.entity_id] = ent
        return ent

    def on_named_entity_spawn(self, p) -> Player:
        """Player spawn — type is always Player."""
        ent = _PLAYER_CLS(
            eid=p.entity_id,
            uuid=p.player_uuid,
            x=p.x, y=p.y, z=p.z,
            yaw=p.yaw * _ANGLE_FROM_BYTE,
            pitch=p.pitch * _ANGLE_FROM_BYTE,
            on_ground=False,
        )
        self._entities[p.entity_id] = ent
        return ent

    def on_spawn_experience_orb(self, p) -> Entity | None:
        # XP orbs are rarely useful for the bot; we just stash a generic Entity.
        ent = Entity(
            eid=p.entity_id,
            uuid=getattr(p, "uuid", None) or _ZERO_UUID,
            x=p.x, y=p.y, z=p.z,
            on_ground=False,
        )
        self._entities[p.entity_id] = ent
        return ent

    def on_entity_metadata(self, p) -> None:
        ent = self._entities.get(p.entity_id)
        if ent is None:
            return
        # Decode the metadata stream and merge — partial updates are
        # common (a single index per packet).
        try:
            decoded = _metadata.read(_Reader(p.metadata))
        except Exception:
            return
        ent.metadata.update(decoded)

    def on_rel_entity_move(self, p) -> None:
        ent = self._entities.get(p.entity_id)
        if ent is None:
            return
        ent.x += p.dx / _REL_MOVE_DIV
        ent.y += p.dy / _REL_MOVE_DIV
        ent.z += p.dz / _REL_MOVE_DIV
        ent.on_ground = p.on_ground

    def on_entity_move_look(self, p) -> None:
        ent = self._entities.get(p.entity_id)
        if ent is None:
            return
        ent.x += p.dx / _REL_MOVE_DIV
        ent.y += p.dy / _REL_MOVE_DIV
        ent.z += p.dz / _REL_MOVE_DIV
        ent.yaw = p.yaw * _ANGLE_FROM_BYTE
        ent.pitch = p.pitch * _ANGLE_FROM_BYTE
        ent.on_ground = p.on_ground

    def on_entity_look(self, p) -> None:
        ent = self._entities.get(p.entity_id)
        if ent is None:
            return
        ent.yaw = p.yaw * _ANGLE_FROM_BYTE
        ent.pitch = p.pitch * _ANGLE_FROM_BYTE
        ent.on_ground = p.on_ground

    def on_entity_teleport(self, p) -> None:
        ent = self._entities.get(p.entity_id)
        if ent is None:
            return
        ent.x = p.x
        ent.y = p.y
        ent.z = p.z
        ent.yaw = p.yaw * _ANGLE_FROM_BYTE
        ent.pitch = p.pitch * _ANGLE_FROM_BYTE
        ent.on_ground = p.on_ground

    def on_entity_velocity(self, p) -> None:
        ent = self._entities.get(p.entity_id)
        if ent is None:
            return
        ent.vx = p.vx / _VELOCITY_DIV
        ent.vy = p.vy / _VELOCITY_DIV
        ent.vz = p.vz / _VELOCITY_DIV

    def on_entity_head_rotation(self, p) -> None:
        # We store head yaw in the metadata dict — the codegen subclasses
        # expose a typed accessor for the index that carries it. For
        # tracker-level use we don't need a dedicated field.
        pass

    def on_entity_destroy(self, p) -> None:
        for eid in p.entity_ids:
            self._entities.pop(eid, None)


# Bootstrap a UUID for entities (e.g., XP orbs) whose spawn packet
# doesn't carry one. We use the all-zero UUID since it never collides
# with a real Mojang UUID.
from uuid import UUID as _UUID

_ZERO_UUID = _UUID("00000000-0000-0000-0000-000000000000")


__all__ = ["EntityTracker"]
