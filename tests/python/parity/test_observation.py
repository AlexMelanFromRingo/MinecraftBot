"""T045 — parity for snapshot / observation."""

from __future__ import annotations

import minecraft_bot_accel
from minecraft_bot.bot import Bot as PyBot


def test_snapshot_observation_present():
    accel = minecraft_bot_accel.Bot.offline("172.26.160.1", 25565, "ParityProbe")
    py = PyBot.offline(host="172.26.160.1", port=25565, username="ParityProbe")
    for name in ("snapshot", "observation"):
        assert hasattr(py, name), f"python ref missing {name}"
        assert hasattr(accel, name), f"accel missing {name}"
