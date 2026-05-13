"""Auto-eat picker integration tests (T067)."""

from __future__ import annotations

from minecraft_bot.foods import (
    FoodInfo,
    pick_highest_saturation,
    pick_minimum_waste,
    pick_most_food_points,
)


def _foods(*names: str) -> list[FoodInfo]:
    from minecraft_bot.foods import get_by_name
    out = []
    for n in names:
        info = get_by_name(n)
        assert info is not None, f"unknown food {n}"
        out.append(info)
    return out


def test_pick_highest_saturation_prefers_steak() -> None:
    pool = _foods("rotten_flesh", "bread", "cooked_beef")
    assert pick_highest_saturation(pool).name == "minecraft:cooked_beef"


def test_pick_most_food_points_prefers_largest() -> None:
    pool = _foods("apple", "bread", "cooked_beef")
    assert pick_most_food_points(pool).name == "minecraft:cooked_beef"


def test_pick_minimum_waste_picks_smallest_sufficient() -> None:
    pool = _foods("apple", "bread", "cooked_beef")
    # need 5 fp, bread = 5 → bread wins
    assert pick_minimum_waste(pool, missing_food_points=5).name == "minecraft:bread"


def test_pick_minimum_waste_falls_back_when_too_hungry() -> None:
    pool = _foods("apple")
    # need 20 fp, only have apple (4 fp) → return apple as fallback
    assert pick_minimum_waste(pool, missing_food_points=20).name == "minecraft:apple"


def test_pick_with_empty_list_returns_none() -> None:
    assert pick_highest_saturation([]) is None
    assert pick_most_food_points([]) is None
    assert pick_minimum_waste([], missing_food_points=5) is None
