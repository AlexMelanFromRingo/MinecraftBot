"""T034 — parity for combat methods (attack, interact_entity, use_item).

Shape parity only. Live packet-trace parity belongs in the integration
suite (T035).
"""

from __future__ import annotations

import inspect

import minecraft_bot_accel
from minecraft_bot.bot import Bot as PyBot

METHODS = ("attack", "interact_entity", "use_item")


def test_combat_methods_present_on_both_backends():
    accel = minecraft_bot_accel.Bot.offline("172.26.160.1", 25565, "ParityProbe")
    py = PyBot.offline(host="172.26.160.1", port=25565, username="ParityProbe")
    for name in METHODS:
        assert hasattr(py, name), f"python ref missing {name}"
        assert hasattr(accel, name), f"accel missing {name}"


def test_combat_methods_are_async():
    py = PyBot.offline(host="172.26.160.1", port=25565, username="ParityProbe")
    for name in METHODS:
        assert inspect.iscoroutinefunction(getattr(py, name)), f"python {name} async"
