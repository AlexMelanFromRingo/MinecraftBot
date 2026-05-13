"""LLM-callable tools wrapping the Bot API.

Each tool exposes a JSON-schema-style signature compatible with both
Anthropic's function-calling and OpenAI's. Use :func:`default_toolset`
to get the standard set; pass it to whichever LLM SDK you're using.

Example::

    from minecraft_bot.bot import Bot
    from minecraft_bot.llm_agent import default_toolset, run_step

    async with Bot.offline(...) as bot:
        toolset = default_toolset()
        # ... LLM returns a tool-use turn ...
        result = await run_step(bot, toolset, "walk_to", {"x": 0, "y": 64, "z": 0})
        print(result)
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

# A tool implementation gets (bot, **kwargs) and returns a string.
ToolFn = Callable[..., Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class Tool:
    """Function-calling tool description.

    Compatible with both Anthropic's ``input_schema`` and OpenAI's
    ``parameters`` shape — the dicts are the same JSONSchema dialect.
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    fn: ToolFn

    def anthropic_schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    def openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


@dataclass(slots=True)
class Toolset:
    """A registry of :class:`Tool` instances."""

    tools: dict[str, Tool] = field(default_factory=dict)

    def add(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self.tools.get(name)

    def anthropic_schemas(self) -> list[dict[str, Any]]:
        return [t.anthropic_schema() for t in self.tools.values()]

    def openai_schemas(self) -> list[dict[str, Any]]:
        return [t.openai_schema() for t in self.tools.values()]

    def names(self) -> list[str]:
        return sorted(self.tools.keys())


async def run_step(bot, toolset: Toolset, name: str, args: dict[str, Any]) -> Any:
    """Execute one tool call by name. Returns whatever the tool returns
    (string, dict, etc.) or raises :class:`KeyError` if no such tool."""
    tool = toolset.get(name)
    if tool is None:
        raise KeyError(f"tool {name!r} not registered (have: {sorted(toolset.tools)})")
    return await tool.fn(bot, **args)


# ---------------------------------------------------------------------------
# Built-in tools — one per common Bot action. Schemas use only basic types
# (string / integer / number / boolean) so any LLM can use them.
# ---------------------------------------------------------------------------


async def _walk_to(bot, x: float, y: float, z: float, timeout: float = 60.0) -> dict:
    try:
        await bot.walk_to(x, y, z, timeout=timeout)
        return {"ok": True, "position": list(bot.position)}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)}


async def _look_at(bot, x: float, y: float, z: float) -> dict:
    await bot.look_at(x, y, z)
    return {"ok": True, "yaw": bot.yaw, "pitch": bot.pitch}


async def _attack(bot, eid: int) -> dict:
    try:
        await bot.attack(eid)
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)}


async def _say(bot, message: str) -> dict:
    await bot.say(message)
    return {"ok": True}


async def _command(bot, command: str) -> dict:
    await bot.command(command)
    return {"ok": True}


async def _dig(bot, x: int, y: int, z: int) -> dict:
    try:
        await bot.dig(x, y, z)
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)}


async def _drop_item(bot, drop_stack: bool = False) -> dict:
    await bot.drop_item(drop_stack=drop_stack)
    return {"ok": True}


async def _select_slot(bot, hotbar_index: int) -> dict:
    await bot.select_slot(hotbar_index)
    return {"ok": True, "held_slot": bot.held_slot}


async def _observe(bot, voxel_radius: int = 4, nearby_radius: float = 16.0) -> dict:
    from minecraft_bot.llm_agent.observation_summary import describe_observation
    obs = bot.observation(voxel_radius=voxel_radius, nearby_radius=nearby_radius)
    return describe_observation(obs)


async def _find_blocks(bot, name: str, radius: int = 32, limit: int = 5) -> dict:
    positions = bot.find_blocks_nearby(name, radius=radius, limit=limit)
    return {"positions": positions}


async def _nearby_entities(bot, radius: float = 32.0) -> dict:
    out = []
    for e in bot.nearby_entities(radius=radius):
        out.append({
            "eid": e.eid,
            "type": type(e).__name__,
            "x": round(e.x, 1),
            "y": round(e.y, 1),
            "z": round(e.z, 1),
            "health": round(float(getattr(e, "health", 0) or 0), 1),
        })
    return {"entities": out}


async def _open_chest(bot, x: int, y: int, z: int) -> dict:
    try:
        wid = await bot.open_chest(x, y, z, timeout=6.0)
        items = []
        for i, slot in enumerate(bot.inventory.container_items()):
            if slot is not None:
                items.append({"slot": i, "name": slot.name, "count": slot.count})
        return {"ok": True, "window_id": wid, "items": items}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)}


async def _close_container(bot) -> dict:
    await bot.close_container()
    return {"ok": True}


async def _inventory(bot) -> dict:
    items = []
    for i, slot in enumerate(bot.inventory.items()):
        if slot is not None:
            items.append({"slot": i, "name": slot.name, "count": slot.count})
    return {"items": items}


def default_toolset() -> Toolset:
    """Standard tool registry covering most use cases."""
    ts = Toolset()
    ts.add(Tool(
        name="walk_to",
        description="Walk to world coordinates (x, y, z). May raise NoPathFound or WalkTimeout.",
        input_schema={
            "type": "object",
            "properties": {
                "x": {"type": "number"},
                "y": {"type": "number"},
                "z": {"type": "number"},
                "timeout": {"type": "number", "default": 60.0},
            },
            "required": ["x", "y", "z"],
        },
        fn=_walk_to,
    ))
    ts.add(Tool(
        name="look_at",
        description="Rotate the bot to face world point (x, y, z). Send PositionLook serverbound.",
        input_schema={
            "type": "object",
            "properties": {
                "x": {"type": "number"}, "y": {"type": "number"}, "z": {"type": "number"},
            },
            "required": ["x", "y", "z"],
        },
        fn=_look_at,
    ))
    ts.add(Tool(
        name="attack",
        description="Attack the entity with given entity id (eid).",
        input_schema={
            "type": "object",
            "properties": {"eid": {"type": "integer"}},
            "required": ["eid"],
        },
        fn=_attack,
    ))
    ts.add(Tool(
        name="say",
        description="Send a chat message visible to all players.",
        input_schema={
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
        fn=_say,
    ))
    ts.add(Tool(
        name="command",
        description="Run a slash command (without the leading '/'). Requires op.",
        input_schema={
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
        fn=_command,
    ))
    ts.add(Tool(
        name="dig",
        description="Break the block at (x, y, z) using the currently-held tool.",
        input_schema={
            "type": "object",
            "properties": {
                "x": {"type": "integer"}, "y": {"type": "integer"}, "z": {"type": "integer"},
            },
            "required": ["x", "y", "z"],
        },
        fn=_dig,
    ))
    ts.add(Tool(
        name="drop_item",
        description="Drop the item in the bot's currently-held hotbar slot.",
        input_schema={
            "type": "object",
            "properties": {
                "drop_stack": {"type": "boolean", "default": False},
            },
        },
        fn=_drop_item,
    ))
    ts.add(Tool(
        name="select_slot",
        description="Select hotbar slot 0..8 as the active held item.",
        input_schema={
            "type": "object",
            "properties": {"hotbar_index": {"type": "integer", "minimum": 0, "maximum": 8}},
            "required": ["hotbar_index"],
        },
        fn=_select_slot,
    ))
    ts.add(Tool(
        name="observe",
        description=(
            "Return a compact JSON summary of the bot's pose, vitals, "
            "what it's looking at, blocks within a small voxel cube, "
            "and nearby entities. Use this to decide what to do next."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "voxel_radius": {"type": "integer", "default": 4},
                "nearby_radius": {"type": "number", "default": 16.0},
            },
        },
        fn=_observe,
    ))
    ts.add(Tool(
        name="find_blocks",
        description="Find the closest blocks by name (e.g. 'oak_log') within radius.",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "radius": {"type": "integer", "default": 32},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["name"],
        },
        fn=_find_blocks,
    ))
    ts.add(Tool(
        name="nearby_entities",
        description="List entities (mobs, players, items) within radius, sorted by distance.",
        input_schema={
            "type": "object",
            "properties": {"radius": {"type": "number", "default": 32.0}},
        },
        fn=_nearby_entities,
    ))
    ts.add(Tool(
        name="open_chest",
        description="Right-click a chest/barrel/dispenser at (x, y, z) and return its contents.",
        input_schema={
            "type": "object",
            "properties": {
                "x": {"type": "integer"}, "y": {"type": "integer"}, "z": {"type": "integer"},
            },
            "required": ["x", "y", "z"],
        },
        fn=_open_chest,
    ))
    ts.add(Tool(
        name="close_container",
        description="Close any open container window.",
        input_schema={"type": "object", "properties": {}},
        fn=_close_container,
    ))
    ts.add(Tool(
        name="inventory",
        description="List the bot's inventory items with slot indices.",
        input_schema={"type": "object", "properties": {}},
        fn=_inventory,
    ))
    return ts


__all__ = ["Tool", "Toolset", "default_toolset", "run_step"]
