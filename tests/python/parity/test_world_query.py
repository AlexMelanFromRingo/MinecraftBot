"""T041 — parity for world-query methods.

9 methods: find_blocks_nearby, nearby_entities, nearby_players,
distance_to, raycast, scan_volume, voxel_grid, chunks_around,
world_map_3d. Shape parity only; semantic parity (correct values
against a live World cache) is verified by the integration test.
"""

from __future__ import annotations

import minecraft_bot_accel
from minecraft_bot.bot import Bot as PyBot


METHODS = (
    "find_blocks_nearby",
    "nearby_entities",
    "nearby_players",
    "distance_to",
    "raycast",
    "scan_volume",
    "voxel_grid",
    "chunks_around",
    "world_map_3d",
)


def test_world_query_methods_present():
    accel = minecraft_bot_accel.Bot.offline("172.26.160.1", 25565, "ParityProbe")
    py = PyBot.offline(host="172.26.160.1", port=25565, username="ParityProbe")
    for name in METHODS:
        assert hasattr(py, name), f"python ref missing {name}"
        assert hasattr(accel, name), f"accel missing {name}"
