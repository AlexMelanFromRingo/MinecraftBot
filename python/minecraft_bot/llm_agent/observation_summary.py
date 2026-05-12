"""Compact text + JSON serialisation of an :class:`Observation`
for LLM consumption.

The LLM doesn't want to see a 9×9×9 voxel grid in raw integers. It
wants something like::

    {
      "pose": {"x": 10000.5, "y": 200.0, "z": 10000.5, "yaw": 0, "pitch": 0,
                "on_ground": true},
      "vitals": {"health": 20, "food": 20},
      "look": {"hit": "minecraft:stone", "distance": 1.6, "face": "top"},
      "around": {
        "stone":   42,    // count of cells in the 9x9x9 grid by name
        "air":     687,
        "water":    0,
        "..."
      },
      "entities_nearby": [
        {"type": "Sheep", "distance": 3.2, "x": 10003, "z": 10000}
      ]
    }
"""

from __future__ import annotations

import json
from collections import Counter
from typing import TYPE_CHECKING, Any

from minecraft_bot.world import block_table

if TYPE_CHECKING:
    from minecraft_bot.observation import Observation


_FACE_NAMES = {0: "bottom", 1: "top", 2: "north", 3: "south", 4: "west", 5: "east"}


def describe_observation(obs: "Observation") -> dict[str, Any]:
    """Return a JSON-serialisable summary of ``obs`` suited for LLM use."""
    # Count block types in the voxel grid.
    block_counts: Counter[str] = Counter()
    for plane in obs.voxel_grid:
        for row in plane:
            for sid in row:
                name = block_table.get_name(sid) or f"id_{sid}"
                # strip "minecraft:" for brevity
                short = name.split(":", 1)[-1]
                block_counts[short] += 1

    around = dict(block_counts.most_common(20))

    look = None
    if obs.look_hit is not None:
        look = {
            "block": obs.look_hit.name,
            "x": obs.look_hit.x,
            "y": obs.look_hit.y,
            "z": obs.look_hit.z,
            "face": _FACE_NAMES.get(obs.look_hit.face, str(obs.look_hit.face)),
            "distance": round(obs.look_hit.distance, 2),
        }

    entities = [
        {
            "type": t,
            "x": round(x, 1),
            "y": round(y, 1),
            "z": round(z, 1),
            "health": round(h, 1),
            "distance": round(((x - obs.x) ** 2 + (z - obs.z) ** 2) ** 0.5, 2),
        }
        for t, x, y, z, h in obs.nearby_entities
    ]

    effects = [
        {"name": n, "level": a + 1, "duration_ticks": d}
        for n, a, d in obs.active_effects
    ]

    return {
        "pose": {
            "x": round(obs.x, 2),
            "y": round(obs.y, 2),
            "z": round(obs.z, 2),
            "yaw": round(obs.yaw, 1),
            "pitch": round(obs.pitch, 1),
            "on_ground": obs.on_ground,
        },
        "vitals": {
            "health": round(obs.health, 1),
            "food": obs.food,
            "saturation": round(obs.saturation, 1),
            "held_slot": obs.held_slot,
        },
        "look": look,
        "around": around,
        "entities_nearby": entities,
        "active_effects": effects,
    }


def describe_observation_text(obs: "Observation") -> str:
    """A short *prose* summary of ``obs`` — good for prompts that don't
    want JSON, or as a "scene description" prefix.
    """
    d = describe_observation(obs)
    pose = d["pose"]
    vit = d["vitals"]
    look = d["look"]
    around = d["around"]
    ents = d["entities_nearby"]
    lines = [
        f"You are at ({pose['x']}, {pose['y']}, {pose['z']}) "
        f"yaw={pose['yaw']:.0f} pitch={pose['pitch']:.0f} "
        f"{'on the ground' if pose['on_ground'] else 'falling'}.",
        f"Health: {vit['health']}/20  Food: {vit['food']}/20  "
        f"Held slot: {vit['held_slot']}.",
    ]
    if look is not None:
        lines.append(
            f"Looking at {look['block']} at ({look['x']}, {look['y']}, "
            f"{look['z']}) on its {look['face']} face, "
            f"{look['distance']} blocks away."
        )
    else:
        lines.append("Looking at open air (no block within 32 blocks).")

    top = ", ".join(f"{n}={c}" for n, c in list(around.items())[:6])
    lines.append(f"Surroundings (9x9x9): {top}")

    if ents:
        ent_strs = [
            f"{e['type']} @ ({e['x']}, {e['y']}, {e['z']}) "
            f"hp={e['health']} dist={e['distance']}"
            for e in ents[:5]
        ]
        lines.append("Nearby entities: " + "; ".join(ent_strs))
    else:
        lines.append("No entities nearby.")

    if d["active_effects"]:
        eff = ", ".join(f"{e['name']} {e['level']}" for e in d["active_effects"])
        lines.append(f"Active effects: {eff}")

    return "\n".join(lines)


def describe_observation_json(obs: "Observation") -> str:
    """Pretty-printed JSON form."""
    return json.dumps(describe_observation(obs), indent=2, ensure_ascii=False)


__all__ = [
    "describe_observation",
    "describe_observation_text",
    "describe_observation_json",
]
