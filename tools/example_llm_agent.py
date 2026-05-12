#!/usr/bin/env python3
"""End-to-end LLM agent example using the Anthropic Messages API.

Sketch: connect a bot, fetch a single observation, ask Claude to
choose one tool to call, execute it, repeat for N steps. This is a
*minimal* loop — production agents would handle multi-turn tool use,
error recovery, conversation memory, etc.

Run::

    pip install anthropic
    export ANTHROPIC_API_KEY=...
    PYTHONPATH=python python tools/example_llm_agent.py

The bot connects to the live test server, teleports to the hazard
arena, and lets Claude drive it for up to 10 tool-use rounds. The
prompt instructs the model to explore the arena and report what it
sees; you'll watch it call ``observe`` → ``walk_to`` → ``observe`` etc.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

from minecraft_bot.bot import Bot
from minecraft_bot.llm_agent import default_toolset, run_step
from minecraft_bot.llm_agent.observation_summary import describe_observation_text

HOST = os.environ.get("MINECRAFT_BOT_TEST_HOST", "172.26.160.1")
PORT = int(os.environ.get("MINECRAFT_BOT_TEST_PORT", "25565"))
USERNAME = os.environ.get("MINECRAFT_BOT_USER", "TestBot1")
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
MAX_ROUNDS = int(os.environ.get("MAX_ROUNDS", "10"))

SYSTEM_PROMPT = """\
You are an AI agent controlling a Minecraft bot. You have access to
the bot's senses and a set of tools to act in the world. Your goal:

1. Use the ``observe`` tool to see your surroundings.
2. Explore the hazard arena east of your spawn at (10000, 200, 10000).
   There are slabs, water, stone ledges and a drop pit east along z=10000.
3. After every action, decide whether you've explored enough or if
   more movement is needed. Say what you see with ``say``.

When you've explored, end with a "say" message summarising what you found.
Use tools efficiently — don't make redundant observations.
"""


async def main() -> int:
    try:
        import anthropic
    except ImportError:
        print("Install the Anthropic SDK: pip install anthropic", file=sys.stderr)
        return 1

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 1

    client = anthropic.AsyncAnthropic()
    toolset = default_toolset()
    tools_schema = toolset.anthropic_schemas()

    async with Bot.offline(HOST, PORT, USERNAME) as bot:
        await bot.command(f"tp {USERNAME} 10000 200 10000")
        await asyncio.sleep(3.0)

        # Conversation history (Anthropic Messages API format).
        messages: list[dict] = [{
            "role": "user",
            "content": (
                f"You just spawned in. Your current pose:\n"
                f"{describe_observation_text(bot.observation())}\n\n"
                f"Begin exploring. Use the tools provided."
            ),
        }]

        for round_idx in range(MAX_ROUNDS):
            print(f"\n--- round {round_idx + 1}/{MAX_ROUNDS} ---")
            resp = await client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=tools_schema,
                messages=messages,
            )

            messages.append({"role": "assistant", "content": resp.content})

            # If the model returned no tool_use, we're done.
            tool_uses = [b for b in resp.content if b.type == "tool_use"]
            for b in resp.content:
                if b.type == "text" and b.text.strip():
                    print(f"[claude] {b.text.strip()[:300]}")

            if not tool_uses:
                print("[done] no more tool calls; exit.")
                break

            # Execute each tool the model requested in this turn.
            tool_results = []
            for tu in tool_uses:
                print(f"[tool ] {tu.name}({json.dumps(tu.input)[:120]})")
                try:
                    result = await run_step(bot, toolset, tu.name, dict(tu.input))
                except Exception as exc:
                    result = {"error": type(exc).__name__, "detail": str(exc)}
                print(f"[ret  ] {json.dumps(result)[:160]}")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": json.dumps(result),
                })

            messages.append({"role": "user", "content": tool_results})

        # Print final bot state.
        print("\n=== final ===")
        print(describe_observation_text(bot.observation()))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
