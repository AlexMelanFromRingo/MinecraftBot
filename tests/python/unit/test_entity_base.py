"""Entity base-class tests (T025)."""

from __future__ import annotations

from uuid import uuid4

from minecraft_bot.codec import metadata as md
from minecraft_bot.entities.base import (
    Entity, ItemEntity, LivingEntity, Mob, Player, Projectile,
)
from minecraft_bot.entities.types import LOOKUP, lookup_class


def _u() -> "UUID":  # type: ignore[name-defined]
    return uuid4()


def test_entity_default_accessors_return_safe_defaults() -> None:
    e = Entity(eid=1, uuid=_u())
    assert e.flags == 0
    assert e.is_on_fire is False
    assert e.is_sprinting is False
    assert e.air_ticks == 300
    assert e.custom_name is None
    assert e.no_gravity is False


def test_entity_flag_bits_decode() -> None:
    e = Entity(eid=1, uuid=_u())
    e.metadata[0] = (md.T_BYTE, 0x08 | 0x40)  # sprinting + glowing
    assert e.is_sprinting
    assert e.is_glowing
    assert not e.is_on_fire


def test_living_entity_health_arrows() -> None:
    le = LivingEntity(eid=2, uuid=_u())
    le.metadata[9] = (md.T_FLOAT, 17.5)
    le.metadata[12] = (md.T_VARINT, 3)
    assert le.health == 17.5
    assert le.is_alive
    assert le.arrows_stuck == 3


def test_living_entity_dead() -> None:
    le = LivingEntity(eid=2, uuid=_u())
    le.metadata[9] = (md.T_FLOAT, 0.0)
    assert not le.is_alive


def test_mob_aggressive_flag() -> None:
    m = Mob(eid=3, uuid=_u())
    m.metadata[15] = (md.T_BYTE, 0x04)
    assert m.is_aggressive
    assert not m.has_no_ai


def test_player_score_main_hand() -> None:
    p = Player(eid=4, uuid=_u())
    p.metadata[16] = (md.T_VARINT, 1234)
    p.metadata[18] = (md.T_BYTE, 0)  # left-handed
    assert p.score == 1234
    assert p.main_hand == 0


def test_lookup_resolves_known_type_ids() -> None:
    """Spot-check that the codegen wired up well-known type IDs."""
    assert lookup_class(54).__name__ == "Item"
    assert lookup_class(82).__name__ == "Sheep"
    assert lookup_class(118).__name__ == "Zombie"
    assert lookup_class(122).__name__ == "Player"


def test_lookup_unknown_type_returns_entity() -> None:
    assert lookup_class(9999) is Entity


def test_generated_subclass_inherits_base_accessors() -> None:
    """A generated Player subclass should still expose ``flags`` etc."""
    cls = lookup_class(122)
    inst = cls(eid=5, uuid=_u())
    assert hasattr(inst, "flags")
    assert hasattr(inst, "is_sprinting")
    assert hasattr(inst, "health")
    inst.metadata[0] = (md.T_BYTE, 0x08)
    assert inst.is_sprinting


def test_lookup_table_size() -> None:
    assert len(LOOKUP) == 124
