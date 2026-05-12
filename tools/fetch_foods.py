#!/usr/bin/env python3
"""Derive ``protocol-data/v763/food_table.json`` from the raw
PrismarineJS ``foods.json`` snapshot.

Output schema::

    {
      "<item_id_str>": {
        "name": "minecraft:apple",
        "food_points": 4,
        "saturation_modifier": 2.4,
        "can_always_eat": false
      },
      ...
    }
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_PATH = REPO_ROOT / "protocol-data" / "v763" / "foods.json"
OUT_PATH = REPO_ROOT / "protocol-data" / "v763" / "food_table.json"


def main() -> int:
    raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for entry in raw:
        item_id = entry["id"]
        # PrismarineJS's `foodPoints` is the hunger restored; `saturation`
        # is the saturation **value** restored (NOT the modifier). The
        # vanilla saturation modifier = saturation / (foodPoints * 2).
        # We store both for downstream consumers.
        food_points = int(entry["foodPoints"])
        saturation = float(entry["saturation"])
        saturation_modifier = saturation / (food_points * 2) if food_points > 0 else 0.0
        out[str(item_id)] = {
            "name": f"minecraft:{entry['name']}",
            "food_points": food_points,
            "saturation": saturation,
            "saturation_modifier": round(saturation_modifier, 4),
            "can_always_eat": False,  # not in upstream; default false
        }
    OUT_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"wrote {len(out)} food entries to {OUT_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
