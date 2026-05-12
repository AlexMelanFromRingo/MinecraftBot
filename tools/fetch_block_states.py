#!/usr/bin/env python3
"""Derive ``protocol-data/v763/block_states.json`` from the raw
PrismarineJS ``blocks.json`` snapshot.

Output schema::

    {
      "<state_id_str>": {
        "name": "minecraft:stone",
        "properties": {}      # state-specific properties (e.g., "facing": "north")
      },
      ...
    }

Run once after pulling a new ``blocks.json``:

    python tools/fetch_block_states.py
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_PATH = REPO_ROOT / "protocol-data" / "v763" / "blocks.json"
OUT_PATH = REPO_ROOT / "protocol-data" / "v763" / "block_states.json"


def main() -> int:
    """Produce two outputs in one file:

    - ``state_to_block``: state_id (str) -> block_name. Every state ID
      in the range ``[minStateId, maxStateId]`` of a block maps to that
      block's name.
    - ``block_table``: block_name -> {hardness, diggable, transparent,
      material, default_state}. Classification metadata at the block
      level; per-state property variations are inferred from
      ``minStateId``/``maxStateId`` offsets when needed by the runtime.

    PrismarineJS's blocks.json describes state PROPERTIES (snowy: bool,
    facing: enum, …) without per-state IDs — the state IDs are
    contiguous from ``minStateId`` to ``maxStateId``. The
    block-level metadata is uniform across all that block's states
    and that's what we need for is_solid / is_water / is_navigable
    classification.
    """
    raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    state_to_block: dict[str, str] = {}
    block_table: dict[str, dict] = {}

    for block in raw:
        name = f"minecraft:{block['name']}"
        # State range
        lo = block["minStateId"]
        hi = block["maxStateId"]
        for sid in range(lo, hi + 1):
            state_to_block[str(sid)] = name
        # Block-level metadata
        block_table[name] = {
            "id": block["id"],
            "default_state": block.get("defaultState", lo),
            "min_state": lo,
            "max_state": hi,
            "hardness": block.get("hardness", 0.0),
            "resistance": block.get("resistance", 0.0),
            "diggable": block.get("diggable", False),
            "transparent": block.get("transparent", False),
            "material": block.get("material", "default"),
            "requires_tool": bool(block.get("harvestTools")),
            "emit_light": block.get("emitLight", 0),
            "filter_light": block.get("filterLight", 0),
            "stack_size": block.get("stackSize", 64),
            # Property names only (values stay implicit by state offset).
            "property_names": [s.get("name") for s in (block.get("states") or [])],
        }

    out = {
        "state_to_block": state_to_block,
        "block_table": block_table,
    }
    OUT_PATH.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {len(state_to_block)} state IDs and {len(block_table)} block entries to {OUT_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
