"""StatusEffects tests (T065)."""

from __future__ import annotations

from minecraft_bot.protocol.v763.packets.play.clientbound.entity_effect import (
    EntityEffect,
)
from minecraft_bot.protocol.v763.packets.play.clientbound.remove_entity_effect import (
    RemoveEntityEffect,
)
from minecraft_bot.status_effects import (
    FLAG_AMBIENT,
    FLAG_SHOW_ICON,
    StatusEffects,
)


def test_apply_effect_then_query() -> None:
    eff = StatusEffects(bot_eid=42)
    eff.on_entity_effect(EntityEffect(
        entity_id=42, effect_id=1, amplifier=0, duration=200, flags=0,
        factor_codec=None,
    ))
    assert eff.has_effect(1)
    assert eff.has_effect("speed")
    entry = eff.get("speed")
    assert entry.duration_ticks == 200
    assert entry.level == 1
    assert entry.amplifier == 0


def test_amplifier_level_relationship() -> None:
    eff = StatusEffects(bot_eid=42)
    eff.on_entity_effect(EntityEffect(
        entity_id=42, effect_id=5, amplifier=2, duration=400, flags=0,
        factor_codec=None,
    ))
    entry = eff.get("strength")
    assert entry.amplifier == 2
    assert entry.level == 3


def test_remove_effect_drops_it() -> None:
    eff = StatusEffects(bot_eid=42)
    eff.on_entity_effect(EntityEffect(
        entity_id=42, effect_id=1, amplifier=0, duration=200, flags=0,
        factor_codec=None,
    ))
    eff.on_remove_entity_effect(RemoveEntityEffect(entity_id=42, effect_id=1))
    assert not eff.has_effect("speed")
    assert len(eff) == 0


def test_other_entity_effect_ignored() -> None:
    eff = StatusEffects(bot_eid=42)
    eff.on_entity_effect(EntityEffect(
        entity_id=999, effect_id=1, amplifier=0, duration=200, flags=0,
        factor_codec=None,
    ))
    assert not eff.has_effect("speed")


def test_flags_decoded() -> None:
    eff = StatusEffects(bot_eid=42)
    flags = FLAG_AMBIENT | FLAG_SHOW_ICON
    eff.on_entity_effect(EntityEffect(
        entity_id=42, effect_id=1, amplifier=0, duration=200, flags=flags,
        factor_codec=None,
    ))
    entry = eff.get("speed")
    assert entry.is_ambient
    assert entry.show_icon
    assert not entry.show_particles


def test_active_effects_lists_all() -> None:
    eff = StatusEffects(bot_eid=42)
    for eid in (1, 5, 10):
        eff.on_entity_effect(EntityEffect(
            entity_id=42, effect_id=eid, amplifier=0, duration=100, flags=0,
            factor_codec=None,
        ))
    names = sorted(eff.names())
    assert names == ["regeneration", "speed", "strength"]


def test_unknown_id_uses_fallback_name() -> None:
    eff = StatusEffects(bot_eid=42)
    eff.on_entity_effect(EntityEffect(
        entity_id=42, effect_id=999, amplifier=0, duration=100, flags=0,
        factor_codec=None,
    ))
    entry = eff.get(999)
    assert entry.name == "effect_999"
