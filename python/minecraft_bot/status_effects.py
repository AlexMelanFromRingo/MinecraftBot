"""Status-effect tracker for the bot (T064).

The bot subscribes to ``entity_effect`` and ``remove_entity_effect``
clientbound packets, filters by its own entity id, and exposes
``has_effect`` / ``active_effects`` queries.

Effect IDs are the vanilla registry numbers (1..43 in 1.20.1). The
common ones, with their canonical names, are listed in ``EFFECT_NAMES``
for ergonomic lookup; unknown IDs are kept as numbers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional


# Subset of 1.20.1 effect registry — the rest still works numerically.
EFFECT_NAMES: dict[int, str] = {
    1: "speed",
    2: "slowness",
    3: "haste",
    4: "mining_fatigue",
    5: "strength",
    6: "instant_health",
    7: "instant_damage",
    8: "jump_boost",
    9: "nausea",
    10: "regeneration",
    11: "resistance",
    12: "fire_resistance",
    13: "water_breathing",
    14: "invisibility",
    15: "blindness",
    16: "night_vision",
    17: "hunger",
    18: "weakness",
    19: "poison",
    20: "wither",
    21: "health_boost",
    22: "absorption",
    23: "saturation",
    24: "glowing",
    25: "levitation",
    26: "luck",
    27: "unluck",
    28: "slow_falling",
    29: "conduit_power",
    30: "dolphins_grace",
    31: "bad_omen",
    32: "hero_of_the_village",
    33: "darkness",
}
EFFECT_IDS: dict[str, int] = {v: k for k, v in EFFECT_NAMES.items()}

FLAG_AMBIENT = 0x01
FLAG_SHOW_PARTICLES = 0x02
FLAG_SHOW_ICON = 0x04


@dataclass(frozen=True, slots=True)
class EffectEntry:
    """One active status effect on the bot."""

    id: int                    # registry id
    amplifier: int             # 0 = level I, 1 = level II, ...
    duration_ticks: int        # remaining; -1 = infinite
    is_ambient: bool
    show_particles: bool
    show_icon: bool

    @property
    def name(self) -> str:
        return EFFECT_NAMES.get(self.id, f"effect_{self.id}")

    @property
    def level(self) -> int:
        return self.amplifier + 1


class StatusEffects:
    """Mutable per-bot tracker of active potion effects.

    The bot owns one instance and wires it to its Connection's
    ``entity_effect`` / ``remove_entity_effect`` subscriptions
    (filtered by ``bot_eid``).
    """

    __slots__ = ("_effects", "bot_eid")

    def __init__(self, *, bot_eid: Optional[int] = None) -> None:
        self._effects: dict[int, EffectEntry] = {}
        self.bot_eid = bot_eid

    def __len__(self) -> int:
        return len(self._effects)

    def __contains__(self, key: object) -> bool:
        if isinstance(key, int):
            return key in self._effects
        if isinstance(key, str):
            eid = EFFECT_IDS.get(key)
            return eid is not None and eid in self._effects
        return False

    # --- packet handlers ----------------------------------------------

    def on_entity_effect(self, p) -> None:
        """``entity_effect`` clientbound — add or update an effect."""
        if self.bot_eid is not None and p.entity_id != self.bot_eid:
            return
        flags = p.flags
        self._effects[p.effect_id] = EffectEntry(
            id=p.effect_id,
            amplifier=p.amplifier,
            duration_ticks=p.duration,
            is_ambient=bool(flags & FLAG_AMBIENT),
            show_particles=bool(flags & FLAG_SHOW_PARTICLES),
            show_icon=bool(flags & FLAG_SHOW_ICON),
        )

    def on_remove_entity_effect(self, p) -> None:
        """``remove_entity_effect`` clientbound — drop the effect."""
        if self.bot_eid is not None and p.entity_id != self.bot_eid:
            return
        self._effects.pop(p.effect_id, None)

    # --- public query API ---------------------------------------------

    def has_effect(self, key: int | str) -> bool:
        return key in self

    def get(self, key: int | str) -> Optional[EffectEntry]:
        if isinstance(key, str):
            eid = EFFECT_IDS.get(key)
            if eid is None:
                return None
            return self._effects.get(eid)
        return self._effects.get(key)

    def active_effects(self) -> list[EffectEntry]:
        return list(self._effects.values())

    def names(self) -> list[str]:
        return [e.name for e in self._effects.values()]


__all__ = [
    "EffectEntry", "StatusEffects",
    "EFFECT_NAMES", "EFFECT_IDS",
    "FLAG_AMBIENT", "FLAG_SHOW_PARTICLES", "FLAG_SHOW_ICON",
]
