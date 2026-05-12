"""BotSnapshot tests (T088)."""

from __future__ import annotations

import pickle

from minecraft_bot.bot import Bot
from minecraft_bot.snapshot import BotSnapshot, EntityRef


def test_snapshot_default_state() -> None:
    bot = Bot.offline("h", 25565, "t")
    snap = bot.snapshot()
    assert isinstance(snap, BotSnapshot)
    assert snap.x == 0.0
    assert snap.y == 64.0
    assert snap.health == 20.0
    assert snap.food == 20
    assert snap.is_dead is False
    assert snap.entity_id is None
    assert snap.is_connected is False


def test_snapshot_immutable_and_hashable() -> None:
    bot = Bot.offline("h", 25565, "t")
    s1 = bot.snapshot()
    s2 = bot.snapshot()
    assert s1 == s2
    assert hash(s1) == hash(s2)


def test_snapshot_picklable() -> None:
    bot = Bot.offline("h", 25565, "t")
    snap = bot.snapshot()
    data = pickle.dumps(snap)
    restored = pickle.loads(data)
    assert restored == snap


def test_snapshot_after_state_change() -> None:
    bot = Bot.offline("h", 25565, "t")
    s1 = bot.snapshot()
    # Mutate bot's internal state directly (simulating server packet).
    bot._health = 12.0
    bot._food = 8
    s2 = bot.snapshot()
    assert s2.health == 12.0
    assert s2.food == 8
    assert s1 != s2


def test_snapshot_inventory_is_tuple_of_length_46() -> None:
    bot = Bot.offline("h", 25565, "t")
    snap = bot.snapshot()
    assert isinstance(snap.inventory, tuple)
    assert len(snap.inventory) == 46
    assert all(s is None for s in snap.inventory)


def test_snapshot_nearby_entities_empty_initially() -> None:
    bot = Bot.offline("h", 25565, "t")
    snap = bot.snapshot()
    assert snap.nearby_entities == ()
