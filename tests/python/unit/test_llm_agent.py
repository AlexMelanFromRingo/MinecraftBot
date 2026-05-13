"""LLM agent: observation summary + tool registry."""

from __future__ import annotations

import asyncio
import json

from minecraft_bot.bot import Bot
from minecraft_bot.llm_agent import default_toolset, describe_observation, run_step
from minecraft_bot.llm_agent.observation_summary import (
    describe_observation_json,
    describe_observation_text,
)
from minecraft_bot.observation import Observation, RayHit


def _bot() -> Bot:
    return Bot.offline("h", 25565, "t")


def _fake_obs() -> Observation:
    return Observation(
        x=10000.5, y=200.0, z=10000.5,
        yaw=0.0, pitch=0.0, on_ground=True,
        health=20.0, food=20, saturation=5.0, held_slot=0,
        look_hit=RayHit(x=10001, y=200, z=10001, state_id=1,
                         name="minecraft:stone", face=1, distance=1.4),
        voxel_radius=2,
        voxel_grid=tuple(tuple(tuple(0 for _ in range(5)) for _ in range(5)) for _ in range(5)),
        voxel_origin=(9998, 198, 9998),
        nearby_entities=(("Sheep", 10003.5, 200.0, 10001.5, 8.0),),
        active_effects=(("speed", 1, 200),),
    )


def test_describe_observation_returns_dict() -> None:
    d = describe_observation(_fake_obs())
    assert d["pose"]["x"] == 10000.5
    assert d["vitals"]["health"] == 20.0
    assert d["look"]["block"] == "minecraft:stone"
    assert d["look"]["face"] == "top"
    assert d["entities_nearby"][0]["type"] == "Sheep"
    assert d["active_effects"][0]["name"] == "speed"


def test_describe_observation_text_contains_key_facts() -> None:
    text = describe_observation_text(_fake_obs())
    assert "10000.5" in text
    assert "Sheep" in text
    assert "speed" in text


def test_describe_observation_json_is_valid_json() -> None:
    s = describe_observation_json(_fake_obs())
    parsed = json.loads(s)
    assert parsed["pose"]["x"] == 10000.5


def test_default_toolset_has_expected_tools() -> None:
    ts = default_toolset()
    expected = {
        "walk_to", "look_at", "attack", "say", "command",
        "dig", "drop_item", "select_slot",
        "observe", "find_blocks", "nearby_entities",
        "open_chest", "close_container", "inventory",
    }
    assert set(ts.names()) >= expected


def test_anthropic_schemas_well_formed() -> None:
    schemas = default_toolset().anthropic_schemas()
    for s in schemas:
        assert "name" in s
        assert "description" in s
        assert "input_schema" in s
        assert s["input_schema"]["type"] == "object"


def test_openai_schemas_well_formed() -> None:
    schemas = default_toolset().openai_schemas()
    for s in schemas:
        assert s["type"] == "function"
        assert "function" in s
        assert "name" in s["function"]


def test_run_step_routes_to_tool() -> None:
    bot = _bot()
    ts = default_toolset()

    async def go():
        result = await run_step(bot, ts, "inventory", {})
        return result

    out = asyncio.run(go())
    assert "items" in out
    assert out["items"] == []   # empty bot


def test_run_step_unknown_tool_raises() -> None:
    bot = _bot()
    ts = default_toolset()

    async def go():
        await run_step(bot, ts, "do_a_barrel_roll", {})

    import pytest
    with pytest.raises(KeyError):
        asyncio.run(go())


def test_observe_tool_returns_summary() -> None:
    """The 'observe' tool calls bot.observation() and serializes it."""
    bot = _bot()
    bot._has_initial_position = True
    bot._physics = bot._physics.__class__(x=8.0, y=64.0, z=8.0, on_ground=True)
    # Without a loaded chunk world_map returns all air (state 0).
    ts = default_toolset()

    async def go():
        return await run_step(bot, ts, "observe", {"voxel_radius": 2})

    out = asyncio.run(go())
    assert "pose" in out and "vitals" in out
    assert out["pose"]["x"] == 8.0
