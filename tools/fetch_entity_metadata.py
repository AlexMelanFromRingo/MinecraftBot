#!/usr/bin/env python3
"""Derive ``protocol-data/v763/entity_metadata.json`` and
``protocol-data/v763/entity_hitboxes.json`` from the raw PrismarineJS
``entities.json`` snapshot.

Output schemas
==============

``entity_metadata.json``::

    {
      "<type_id_str>": {
        "name": "allay",
        "display_name": "Allay",
        "category": "mob",      // mob / object / projectile / player / other / passive / hostile
        "parent_class": "Mob",  // inferred parent — Entity / Living / Mob / Projectile / ItemEntity / Player
        "metadata_keys": [
          {"index": 0, "name": "shared_flags"},
          {"index": 1, "name": "air_supply"},
          ...
        ]
      },
      ...
    }

``entity_hitboxes.json``::

    {
      "<entity_name>": {"width": 0.6, "height": 1.8},
      ...
    }
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_PATH = REPO_ROOT / "protocol-data" / "v763" / "entities.json"
METADATA_OUT = REPO_ROOT / "protocol-data" / "v763" / "entity_metadata.json"
HITBOX_OUT = REPO_ROOT / "protocol-data" / "v763" / "entity_hitboxes.json"


def _infer_parent(category: str, name: str) -> str:
    """Pick the Python base class an entity should inherit from."""
    if name == "player":
        return "Player"
    if name == "item":
        return "ItemEntity"
    if category in ("projectile", ):
        return "Projectile"
    if category in ("object", ):
        return "Entity"  # generic objects (boat, minecart, falling_block, etc.)
    if category in ("other", "ambient", "water_creature", "passive_mobs", "hostile_mobs"):
        return "Mob"
    if category == "mob":
        return "Mob"
    return "Entity"


def main() -> int:
    raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))

    metadata_out: dict[str, dict] = {}
    hitbox_out: dict[str, dict] = {}

    for entry in raw:
        type_id = entry["id"]
        name = entry["name"]
        keys = entry.get("metadataKeys") or []

        metadata_out[str(type_id)] = {
            "name": name,
            "display_name": entry.get("displayName", name),
            "category": entry.get("category", entry.get("type", "other")),
            "parent_class": _infer_parent(entry.get("category", entry.get("type", "other")), name),
            "metadata_keys": [
                {"index": i, "name": k} for i, k in enumerate(keys)
            ],
        }
        hitbox_out[name] = {
            "width": float(entry.get("width", 0.6)),
            "height": float(entry.get("height", 1.8)),
        }

    METADATA_OUT.write_text(json.dumps(metadata_out, indent=2), encoding="utf-8")
    HITBOX_OUT.write_text(json.dumps(hitbox_out, indent=2), encoding="utf-8")
    print(f"wrote {len(metadata_out)} entity types to {METADATA_OUT.relative_to(REPO_ROOT)}")
    print(f"wrote {len(hitbox_out)} hitboxes to {HITBOX_OUT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
