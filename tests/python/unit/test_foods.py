"""Food picker tests (T027-T029)."""

from __future__ import annotations

from minecraft_bot import foods


def test_apple_present_with_expected_stats() -> None:
    apple = foods.get_by_name("apple")
    assert apple is not None
    assert apple.food_points == 4
    assert apple.saturation == 2.4


def test_get_by_name_accepts_minecraft_prefix() -> None:
    a = foods.get_by_name("minecraft:cooked_beef")
    b = foods.get_by_name("cooked_beef")
    assert a is not None and a is b


def test_is_food_for_apple_id() -> None:
    apple = foods.get_by_name("apple")
    assert apple is not None
    assert foods.is_food(apple.item_id)
    assert not foods.is_food(0)
    assert not foods.is_food(99999)


def test_pick_highest_saturation_prefers_steak_over_apple() -> None:
    apple = foods.get_by_name("apple")
    steak = foods.get_by_name("cooked_beef")
    assert apple is not None and steak is not None
    winner = foods.pick_highest_saturation([apple, steak])
    assert winner is steak


def test_pick_most_food_points() -> None:
    apple = foods.get_by_name("apple")              # 4 fp
    bread = foods.get_by_name("bread")              # 5 fp
    steak = foods.get_by_name("cooked_beef")        # 8 fp
    assert all([apple, bread, steak])
    winner = foods.pick_most_food_points([apple, bread, steak])
    assert winner is steak


def test_pick_minimum_waste_chooses_smallest_sufficient() -> None:
    apple = foods.get_by_name("apple")              # 4 fp
    bread = foods.get_by_name("bread")              # 5 fp
    steak = foods.get_by_name("cooked_beef")        # 8 fp
    pool = [apple, bread, steak]
    # need 5 -> bread is smallest >= 5
    assert foods.pick_minimum_waste(pool, missing_food_points=5) is bread


def test_pick_minimum_waste_falls_back_when_nothing_big_enough() -> None:
    apple = foods.get_by_name("apple")
    assert apple is not None
    # need 20 fp, only apple available (4 fp) — fall back to highest fp.
    result = foods.pick_minimum_waste([apple], missing_food_points=20)
    assert result is apple


def test_filter_eatable_keeps_only_food_items() -> None:
    apple = foods.get_by_name("apple")
    assert apple is not None
    items = [(0, apple.item_id), (1, 99999), (2, apple.item_id)]
    out = foods.filter_eatable(items)
    assert len(out) == 2
    assert out[0] == (0, apple)
    assert out[1] == (2, apple)


def test_table_size_sanity() -> None:
    assert 20 <= len(foods.BY_ID) <= 80
