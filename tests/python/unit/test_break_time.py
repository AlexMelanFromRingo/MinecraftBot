"""Break-time calculation tests (T069)."""

from __future__ import annotations

from minecraft_bot.dig import break_seconds, break_ticks


def _within(actual: float, expected: float, *, tol: float = 0.4) -> bool:
    """Within ±tol of expected (loose because we skip several modifiers)."""
    return abs(actual - expected) / expected <= tol


# Reference values from minecraft.wiki Block#Hardness / Breaking time table.

def test_dirt_by_hand_around_750ms() -> None:
    t = break_seconds("dirt")
    assert _within(t, 0.75), f"dirt by hand: {t:.2f}s"


def test_stone_by_wooden_pickaxe_around_1_5s() -> None:
    t = break_seconds("stone", "wooden_pickaxe")
    assert _within(t, 1.15), f"stone by wooden pickaxe: {t:.2f}s"


def test_stone_by_hand_takes_at_least_7s() -> None:
    t = break_seconds("stone")
    assert t > 7.0, f"stone by hand should be slow, got {t:.2f}s"


def test_stone_by_diamond_pickaxe_fast() -> None:
    t = break_seconds("stone", "diamond_pickaxe")
    assert t < 0.4, f"stone by diamond should be quick, got {t:.2f}s"


def test_glass_by_hand_quick() -> None:
    # Glass: hardness 0.3, correct tool = none (instant on break)
    t = break_seconds("glass")
    assert t < 1.0


def test_bedrock_unbreakable() -> None:
    t = break_ticks("bedrock")
    assert t < 0   # unbreakable -> negative ticks


def test_unknown_block_returns_quick() -> None:
    assert break_ticks("not_a_real_block_xyz") == 1
