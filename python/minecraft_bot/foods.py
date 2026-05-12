"""Food picker helpers (T027-T029).

Wraps ``protocol-data/v763/food_table.json``. Used by ``bot.auto_eat``
and ``Bot.eat`` to choose what to chomp.

The Bot itself owns the *selection policy* (per FR-091: caller-supplied
selector). This module provides a few ready-made selectors and the
look-up helpers.

A food info entry is::

    {
        "name": "minecraft:cooked_beef",
        "food_points": 8,
        "saturation": 12.8,
        "saturation_modifier": 0.8,
        "can_always_eat": false,
    }
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
FOOD_PATH = REPO_ROOT / "protocol-data" / "v763" / "food_table.json"

with FOOD_PATH.open("r", encoding="utf-8") as _fh:
    _RAW: dict[str, dict] = json.load(_fh)


@dataclass(frozen=True, slots=True)
class FoodInfo:
    item_id: int
    name: str
    food_points: int
    saturation: float
    saturation_modifier: float
    can_always_eat: bool


def _make(item_id_str: str, entry: dict) -> FoodInfo:
    return FoodInfo(
        item_id=int(item_id_str),
        name=entry["name"],
        food_points=entry["food_points"],
        saturation=entry["saturation"],
        saturation_modifier=entry["saturation_modifier"],
        can_always_eat=entry.get("can_always_eat", False),
    )


BY_ID: dict[int, FoodInfo] = {int(k): _make(k, v) for k, v in _RAW.items()}
BY_NAME: dict[str, FoodInfo] = {v.name: v for v in BY_ID.values()}


def is_food(item_id: int) -> bool:
    """Return True if ``item_id`` is a known food item."""
    return item_id in BY_ID


def get(item_id: int) -> Optional[FoodInfo]:
    return BY_ID.get(item_id)


def get_by_name(name: str) -> Optional[FoodInfo]:
    if ":" not in name:
        name = "minecraft:" + name
    return BY_NAME.get(name)


# --- selectors -----------------------------------------------------------


def pick_highest_saturation(candidates: Iterable[FoodInfo]) -> Optional[FoodInfo]:
    """Return the candidate with the highest saturation gain.

    Ties broken by food_points (higher first), then name (alphabetical
    for determinism).
    """
    pool = list(candidates)
    if not pool:
        return None
    return max(
        pool, key=lambda f: (f.saturation, f.food_points, -ord(f.name[0])),
    )


def pick_most_food_points(candidates: Iterable[FoodInfo]) -> Optional[FoodInfo]:
    """Return the candidate that restores the most hunger bars."""
    pool = list(candidates)
    if not pool:
        return None
    return max(pool, key=lambda f: (f.food_points, f.saturation))


def pick_minimum_waste(
    candidates: Iterable[FoodInfo], *, missing_food_points: int
) -> Optional[FoodInfo]:
    """Pick the smallest food that *still* fills the hunger bar.

    "Minimum waste" = smallest ``food_points >= missing_food_points``.
    Falls back to ``pick_most_food_points`` if no food is large enough.
    """
    pool = list(candidates)
    if not pool:
        return None
    sufficient = [f for f in pool if f.food_points >= missing_food_points]
    if sufficient:
        return min(sufficient, key=lambda f: (f.food_points, -f.saturation))
    return pick_most_food_points(pool)


def filter_eatable(items: Iterable[tuple[int, int]]) -> list[tuple[int, FoodInfo]]:
    """Convert ``[(slot_index, item_id), ...]`` to
    ``[(slot_index, FoodInfo), ...]`` keeping only food items."""
    out: list[tuple[int, FoodInfo]] = []
    for slot_idx, item_id in items:
        info = BY_ID.get(item_id)
        if info is not None:
            out.append((slot_idx, info))
    return out


__all__ = [
    "FoodInfo", "BY_ID", "BY_NAME",
    "is_food", "get", "get_by_name",
    "pick_highest_saturation", "pick_most_food_points",
    "pick_minimum_waste", "filter_eatable",
]
