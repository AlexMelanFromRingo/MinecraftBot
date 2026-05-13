"""T063 + T070 — shape parity for container + high-level task methods."""

from __future__ import annotations

import minecraft_bot_accel
from minecraft_bot.bot import Bot as PyBot

METHODS = (
    # Group G containers
    "open_block_container",
    "open_chest",
    "open_furnace",
    "open_crafting_table",
    "close_container",
    "craft",
    # Group H high-level tasks
    "dig",
    "eat",
    "follow",
    "say",
    "chat",
)


def test_containers_and_tasks_methods_present():
    accel = minecraft_bot_accel.Bot.offline("172.26.160.1", 25565, "ParityProbe")
    py = PyBot.offline(host="172.26.160.1", port=25565, username="ParityProbe")
    for name in METHODS:
        assert hasattr(py, name), f"python ref missing {name}"
        assert hasattr(accel, name), f"accel missing {name}"
