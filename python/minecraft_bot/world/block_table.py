"""Block-state classification table.

Loads ``protocol-data/v763/block_states.json`` at import time and
exposes block-level metadata plus the classification predicates the
World cache / pathfinder / physics tick all rely on.

The data file has two top-level keys:

- ``state_to_block``: ``{state_id_str: block_name}`` for all ~24000
  state IDs in protocol 763.
- ``block_table``: ``{block_name: {id, default_state, min_state,
  max_state, hardness, resistance, diggable, transparent, material,
  emit_light, filter_light, stack_size, property_names}}``.

For state-specific properties (e.g., ``oak_slab[type=top]`` vs
``oak_slab[type=bottom]``), inspect the state-ID offset from
``min_state`` in combination with ``property_names`` (the runtime
property decoder lives in :mod:`world.cache`; this module only stores
the table).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_PATH = REPO_ROOT / "protocol-data" / "v763" / "block_states.json"


@lru_cache(maxsize=1)
def _load() -> tuple[dict[int, str], dict[str, dict]]:
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    state_to_block_str = raw["state_to_block"]
    # Convert keys from str to int once at load time.
    state_to_block = {int(k): v for k, v in state_to_block_str.items()}
    return state_to_block, raw["block_table"]


def get_name(state_id: int) -> str | None:
    """Block name (``"minecraft:stone"``) for ``state_id``, or ``None``
    if the state is unknown."""
    state_to_block, _ = _load()
    return state_to_block.get(state_id)


def get_block_info(state_id: int) -> dict | None:
    """Block-level metadata dict for the block of ``state_id``, or
    ``None`` if unknown."""
    state_to_block, block_table = _load()
    name = state_to_block.get(state_id)
    return block_table.get(name) if name else None


def get_block_info_by_name(name: str) -> dict | None:
    _, block_table = _load()
    return block_table.get(name)


# --- classification predicates --------------------------------------------

# Block names that are "passthrough" — the bot can walk through them.
# Computed from the table on first call; the rule is: bounding_box ==
# "empty" in vanilla. The minecraft-data 1.20 dump doesn't expose
# bounding_box directly per state, so we synthesize this set from a
# curated list of known passthrough names plus "transparent + not
# solid material" heuristics.

_PASSTHROUGH_NAMES: frozenset[str] = frozenset({
    "minecraft:air", "minecraft:cave_air", "minecraft:void_air",
    "minecraft:water", "minecraft:lava", "minecraft:bubble_column",
    "minecraft:grass", "minecraft:tall_grass", "minecraft:fern",
    "minecraft:large_fern", "minecraft:dead_bush", "minecraft:seagrass",
    "minecraft:tall_seagrass", "minecraft:kelp", "minecraft:kelp_plant",
    "minecraft:dandelion", "minecraft:poppy", "minecraft:blue_orchid",
    "minecraft:allium", "minecraft:azure_bluet", "minecraft:red_tulip",
    "minecraft:orange_tulip", "minecraft:white_tulip", "minecraft:pink_tulip",
    "minecraft:oxeye_daisy", "minecraft:cornflower", "minecraft:lily_of_the_valley",
    "minecraft:wither_rose", "minecraft:sunflower", "minecraft:lilac",
    "minecraft:rose_bush", "minecraft:peony", "minecraft:torchflower",
    "minecraft:pitcher_plant",
    "minecraft:torch", "minecraft:wall_torch", "minecraft:soul_torch",
    "minecraft:soul_wall_torch", "minecraft:redstone_torch",
    "minecraft:redstone_wall_torch",
    "minecraft:ladder", "minecraft:vine", "minecraft:rail",
    "minecraft:powered_rail", "minecraft:detector_rail",
    "minecraft:activator_rail", "minecraft:cobweb",
    "minecraft:lever", "minecraft:tripwire", "minecraft:tripwire_hook",
    "minecraft:scaffolding",
    # Snow layers: vanilla treats 1–2-layer snow as walkable (height
    # 0.125–0.25 falls under STEP_HEIGHT=0.6). Without per-state
    # property parsing here we treat ALL snow_layer as passable; the
    # bot may waste a tick stepping into 7-layer snow but won't get
    # stuck on the common 1–2-layer case.
    "minecraft:snow",
    # Sign / banner / item-frame ride-throughs handled separately by
    # the navigable-obstacle predicate.
})

# Block name *prefixes* that classify as navigable obstacles (doors,
# fence gates, trapdoors). These open in-place; pathfinder allows
# traversal at +2.0 cost and the physics tick auto-opens them.
_OBSTACLE_PREFIXES: tuple[str, ...] = (
    "minecraft:oak_door", "minecraft:spruce_door", "minecraft:birch_door",
    "minecraft:jungle_door", "minecraft:acacia_door", "minecraft:dark_oak_door",
    "minecraft:mangrove_door", "minecraft:cherry_door", "minecraft:bamboo_door",
    "minecraft:crimson_door", "minecraft:warped_door", "minecraft:iron_door",
    "minecraft:oak_fence_gate", "minecraft:spruce_fence_gate",
    "minecraft:birch_fence_gate", "minecraft:jungle_fence_gate",
    "minecraft:acacia_fence_gate", "minecraft:dark_oak_fence_gate",
    "minecraft:mangrove_fence_gate", "minecraft:cherry_fence_gate",
    "minecraft:bamboo_fence_gate", "minecraft:crimson_fence_gate",
    "minecraft:warped_fence_gate",
    "minecraft:oak_trapdoor", "minecraft:spruce_trapdoor",
    "minecraft:birch_trapdoor", "minecraft:jungle_trapdoor",
    "minecraft:acacia_trapdoor", "minecraft:dark_oak_trapdoor",
    "minecraft:mangrove_trapdoor", "minecraft:cherry_trapdoor",
    "minecraft:bamboo_trapdoor", "minecraft:crimson_trapdoor",
    "minecraft:warped_trapdoor", "minecraft:iron_trapdoor",
)


def is_solid(state_id: int) -> bool:
    """Block at ``state_id`` is a full-cube solid (pathfinder cannot pass through)."""
    name = get_name(state_id)
    if name is None:
        # Unknown state — conservative default.
        return False
    if name in _PASSTHROUGH_NAMES:
        return False
    if name.startswith(_OBSTACLE_PREFIXES):
        # Navigable obstacle (door/gate/trapdoor) — not strictly solid.
        return False
    info = get_block_info_by_name(name)
    if info is None:
        return False
    # Vanilla heuristic: a block is solid if it's not transparent OR is
    # one of a small set of explicit transparent-but-solid blocks
    # (e.g., glass, leaves). minecraft-data marks leaves transparent
    # but they ARE solid for collision. Pragmatic rule:
    #   - explicitly passthrough/obstacle: handled above
    #   - transparent: NOT solid unless block name says leaves / glass / ice
    if info.get("transparent"):
        if "leaves" in name or "glass" in name or "ice" in name:
            return True
        return False
    return True


def is_water(state_id: int) -> bool:
    name = get_name(state_id)
    if name is None:
        return False
    return name in ("minecraft:water", "minecraft:bubble_column")


def is_lava(state_id: int) -> bool:
    return get_name(state_id) == "minecraft:lava"


def is_navigable_obstacle(state_id: int) -> bool:
    """True for doors / fence gates / trapdoors — pathfinder may cross
    them with a small extra cost; the physics tick opens them in-place
    during traversal."""
    name = get_name(state_id)
    if name is None:
        return False
    return name.startswith(_OBSTACLE_PREFIXES)


def is_passthrough(state_id: int) -> bool:
    """True if the bot can walk through this block without any
    obstacle handling (air, grass, water, torches, …)."""
    name = get_name(state_id)
    if name is None:
        return False
    return name in _PASSTHROUGH_NAMES


def step_height(state_id: int) -> float:
    """The block's effective top-Y for physics step-up. A full cube is
    1.0; a bottom slab is 0.5; a top slab still requires step-up to
    1.0 from below. Stairs vary by orientation — for the pathfinder we
    return 0.5 for any stair (the physics tick can refine).

    For unknown / passthrough / non-solid blocks, returns 0.0.
    """
    if not is_solid(state_id):
        return 0.0
    name = get_name(state_id)
    if name is None:
        return 0.0
    if name.endswith("_slab"):
        # bottom slab: 0.5; top slab: 1.0; double slab: 1.0
        # Without state-level property decode, default to 0.5 (more
        # permissive for pathfinder — physics tick handles precise).
        return 0.5
    if name.endswith("_stairs"):
        return 0.5  # bottom stair half-height (top stair handled by physics)
    return 1.0


__all__ = [
    "get_block_info",
    "get_block_info_by_name",
    "get_name",
    "is_lava",
    "is_navigable_obstacle",
    "is_passthrough",
    "is_solid",
    "is_water",
    "step_height",
]
