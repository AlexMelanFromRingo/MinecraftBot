"""T056 — parity for inventory methods (Group F)."""

from __future__ import annotations

import minecraft_bot_accel
from minecraft_bot.bot import Bot as PyBot


METHODS = (
    "held_item",
    "find_item",
    "count_item",
    "iter_accessible_slots",
    "select_slot",
    "drop_item",
    "click_slot",
    "move_item",
    "quick_move",
    "equip_armor",
    "unequip_armor",
    "swap_to_offhand",
)


def test_inventory_methods_present():
    accel = minecraft_bot_accel.Bot.offline("172.26.160.1", 25565, "ParityProbe")
    py = PyBot.offline(host="172.26.160.1", port=25565, username="ParityProbe")
    for name in METHODS:
        assert hasattr(py, name), f"python ref missing {name}"
        assert hasattr(accel, name), f"accel missing {name}"


def test_itemslot_exposed_on_accel():
    assert hasattr(minecraft_bot_accel, "ItemSlot")
