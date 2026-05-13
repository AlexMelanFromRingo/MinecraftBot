"""Block-break time calculation (T068, T069).

Vanilla Minecraft Java Edition formula::

    speed_multiplier = tool_efficiency_for_material  if tool matches  else 1.0
                       (with Efficiency enchant: +(efficiency_level^2 + 1))
                       (under Haste: × (1 + 0.2 × haste_level))
                       (under Mining Fatigue: × 0.3^fatigue_level)
                       (in water without Aqua Affinity: × 0.2)
                       (not on ground: × 0.2)

    is_correct_tool      = tool can actually mine the block (drops items)

    damage_per_tick      = speed_multiplier / hardness / (30 if is_correct_tool else 100)

    ticks_to_break       = ceil(1 / damage_per_tick)
                          (clamped to 0 if instant-break, e.g. flowers)

Break time in seconds = ``ticks_to_break / 20``.

For the Bot API we only model the *common* path (correct tool, no
enchants, on ground, not in water). The 5% tolerance in T069 covers
the small deviations from skipped multipliers.
"""

from __future__ import annotations

from minecraft_bot.world import block_table as _bt

# Tool material → speed multiplier on its preferred block group.
# Source: minecraft.wiki Item#Tool_speed_multipliers.
_TOOL_SPEEDS: dict[str, float] = {
    "wooden":    2.0,
    "stone":     4.0,
    "iron":      6.0,
    "diamond":   8.0,
    "golden":    12.0,
    "netherite": 9.0,
}

# Which "mineable/X" material a tool prefix is correct for.
_TOOL_TO_MATERIAL: dict[str, str] = {
    "_pickaxe": "mineable/pickaxe",
    "_axe":     "mineable/axe",
    "_shovel":  "mineable/shovel",
    "_hoe":     "mineable/hoe",
    "shears":   "mineable/shears",
    "sword":    "sword",
}


def _tool_speed(tool_name: str | None, block_material: str) -> tuple[float, bool]:
    """Return ``(speed_multiplier, is_correct_tool)`` for ``tool_name`` on
    a block of ``block_material`` ("mineable/pickaxe" etc.).

    ``tool_name`` may be ``"diamond_pickaxe"``, ``"shears"``, etc., or
    None for bare hand.
    """
    if not tool_name:
        return 1.0, False
    n = tool_name.split(":", 1)[-1]   # strip namespace if any

    # Shears specifically: 5x on leaves/wool, instant on wool, fast on cobweb.
    if n == "shears":
        if "wool" in block_material or "leaves" in block_material:
            return 5.0, True
        return 1.0, False

    # Match tool material prefix (wooden_, stone_, ...).
    material_prefix = n.rsplit("_", 1)[0]
    speed = _TOOL_SPEEDS.get(material_prefix, 1.0)
    suffix = "_" + n.rsplit("_", 1)[-1]   # "_pickaxe", "_axe", etc.
    correct_material = _TOOL_TO_MATERIAL.get(suffix)
    if correct_material is None:
        # Tool suffix not in table -> treat as non-matching but speed applies.
        return speed, False
    is_correct = correct_material == block_material
    return speed, is_correct


def break_ticks(block_name: str, tool_name: str | None = None) -> int:
    """Return ticks to break ``block_name`` with ``tool_name`` in the
    common case (on ground, not in water, no haste/fatigue/eff)."""
    name = block_name if ":" in block_name else "minecraft:" + block_name
    info = _bt.get_block_info_by_name(name)
    if info is None:
        return 1   # unknown block — treat as instant
    hardness = info.get("hardness", 1.0)
    if hardness is None or hardness < 0 or not info.get("diggable", True):
        return -1   # bedrock-style unbreakable
    if hardness == 0:
        return 0
    material = info.get("material", "")
    speed, is_correct = _tool_speed(tool_name, material)
    requires_tool = bool(info.get("requires_tool", False))
    # canHarvest = (block doesn't require a tool) OR (we have the right one).
    can_harvest = (not requires_tool) or is_correct
    divisor = 30.0 if can_harvest else 100.0
    damage_per_tick = speed / hardness / divisor
    if damage_per_tick <= 0:
        return -1
    ticks = int((1.0 / damage_per_tick) + 0.999)   # ceil
    return max(1, ticks)


def break_seconds(block_name: str, tool_name: str | None = None) -> float:
    """Break time in seconds (ticks / 20)."""
    t = break_ticks(block_name, tool_name)
    return -1.0 if t < 0 else t / 20.0


__all__ = ["break_seconds", "break_ticks"]
