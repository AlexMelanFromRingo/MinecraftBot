# Quickstart: Bot API

**Date**: 2026-05-12
**Plan**: [plan.md](./plan.md)
**Spec target**: SC-012 (a working "follow this player" bot in < 30 lines).

This document is the canonical "is the Bot API working?" check. Each
section is a copy-pasteable script demonstrating one user story.

---

## Prerequisites

(Same as 001 quickstart; nothing new.)

1. Paper 1.20.1 server reachable at `172.26.160.1:25565` with
   `online-mode=false`.
2. Python 3.11+, virtualenv with the framework installed:
   ```bash
   pip install -e python/[dev]
   ```

---

## US1 — Walk to a coordinate

```python
# tools/quickstart_us1.py
import asyncio
from minecraft_bot import Bot

async def main():
    async with Bot.offline("172.26.160.1", 25565, "WalkBot") as bot:
        await bot.connect()
        print("spawn position:", bot.position)
        target = (int(bot.position[0]) + 50, int(bot.position[1]), int(bot.position[2]) + 50)
        await bot.walk_to(*target, timeout=60)
        print("arrived at:", bot.position)

asyncio.run(main())
```

Expected: bot arrives within 1 block of the target within 60 seconds.

---

## US2 — Observe the world and entities

```python
# tools/quickstart_us2.py
import asyncio
from minecraft_bot import Bot
from minecraft_bot.entities.types import Sheep

async def main():
    async with Bot.offline("172.26.160.1", 25565, "ObserverBot") as bot:
        await bot.connect()
        await asyncio.sleep(2)  # let chunks load
        logs = bot.world.find_blocks_nearby("oak_log", radius=32, limit=5)
        print(f"oak logs nearby: {len(logs)}")
        for pos in logs:
            print(f"  {pos} -> {bot.world.get_block_name(*pos)}")
        sheep = [e for e in bot.entities.nearby_entities(radius=64) if isinstance(e, Sheep)]
        for s in sheep:
            print(f"sheep {s.id}: wool={s.wool_color}, sheared={s.is_sheared}")

asyncio.run(main())
```

---

## US3 — Inventory + chest

```python
# tools/quickstart_us3.py
import asyncio
from minecraft_bot import Bot

CHEST_POS = (5, 64, 5)  # adjust to where you placed a chest

async def main():
    async with Bot.offline("172.26.160.1", 25565, "ChestBot") as bot:
        await bot.connect()
        await bot.command("/give @s diamond_sword")
        await asyncio.sleep(1)
        sword_slot = bot.inventory.find_item("minecraft:diamond_sword")
        print(f"got diamond sword in slot {sword_slot}")

        await bot.walk_to(*CHEST_POS)
        container = await bot.open_chest(*CHEST_POS)
        print(f"chest has {sum(1 for s in container.items() if s is not None)} non-empty slots")
        await bot.close_container()

asyncio.run(main())
```

---

## US4 — Survive: auto-eat + dig + attack

```python
# tools/quickstart_us4.py
import asyncio
from minecraft_bot import Bot
from minecraft_bot.entities.types import Zombie

async def main():
    async with Bot.offline("172.26.160.1", 25565, "SurvivorBot") as bot:
        await bot.connect()
        await bot.command("/gamemode survival")
        await bot.command("/give @s cooked_beef 16")
        bot.auto_eat(threshold=15)  # eat when food < 15

        # Wait for a zombie
        while True:
            zombies = bot.entities.nearby_entities(radius=8, type_filter=Zombie)
            if zombies:
                target = zombies[0]
                print(f"attacking zombie {target.id} at distance {bot.entities.distance_to(target.id):.1f}")
                while target.id in [z.id for z in bot.entities.nearby_entities(8, Zombie)]:
                    await bot.look_at(*target.position)
                    await bot.attack(target.id)
                    await asyncio.sleep(0.6)
                print("zombie killed")
                break
            await asyncio.sleep(0.5)

asyncio.run(main())
```

---

## US5 — Follow a player

```python
# tools/quickstart_us5.py — under 30 lines per SC-012
import asyncio
from minecraft_bot import Bot

TARGET_PLAYER = "Alex_Melan"  # change to your username

async def main():
    async with Bot.offline("172.26.160.1", 25565, "FollowerBot") as bot:
        await bot.connect()
        while True:
            target = next(
                (p for p in bot.entities.nearby_players(64) if p.display_name == TARGET_PLAYER),
                None,
            )
            if target is None:
                print(f"{TARGET_PLAYER} not in view; waiting")
                await asyncio.sleep(2)
                continue
            try:
                await bot.follow(target.id, distance=3, timeout=60)
            except Exception as exc:
                print(f"follow ended: {exc}")
                break

asyncio.run(main())
```

---

## US6 — Behaviour tree composition

```python
# tools/quickstart_us6.py
import asyncio
from minecraft_bot import Bot
from minecraft_bot.behaviour import Selector, Sequence, Condition, EatWhenHungry, AttackNearest, WalkTo
from minecraft_bot.entities.types import Hostile

async def main():
    async with Bot.offline("172.26.160.1", 25565, "BTBot") as bot:
        await bot.connect()
        spawn = bot.position
        tree = Selector([
            Sequence([Condition(lambda b: b.food < 10), EatWhenHungry()]),
            Sequence([Condition(lambda b: b.entities.nearby_entities(8, Hostile)), AttackNearest(Hostile)]),
            WalkTo(int(spawn[0]), int(spawn[1]), int(spawn[2])),
        ])
        await bot.behaviour.run(tree, max_iterations=300)  # ~5 minutes of policy

asyncio.run(main())
```

---

## US7 — Chat & commands

```python
# tools/quickstart_us7.py
import asyncio
from minecraft_bot import Bot, ChatMessageEvent

async def main():
    async with Bot.offline("172.26.160.1", 25565, "ChatBot") as bot:
        await bot.connect()

        @bot.on(ChatMessageEvent)
        def on_chat(event):
            if event.message.startswith("!ping"):
                asyncio.create_task(bot.say(f"pong @{event.sender}"))

        await bot.say("ChatBot online — say !ping to test")
        await asyncio.sleep(600)  # listen for 10 minutes

asyncio.run(main())
```

---

## Verification commands

```bash
# Unit tests (no server needed)
pytest -q tests/python/unit

# Integration tests (server REQUIRED)
pytest -m live -q tests/python/integration

# Performance budgets
pytest -q tests/python/perf

# Full quickstart sweep
for script in tools/quickstart_us{1,2,3,4,5,6,7}.py; do
    python "$script"
done
```

---

## What's NOT covered here

- Online-mode auth (deferred).
- ML / RL adapters (`bot.snapshot()` is available as a substrate;
  numpy / gymnasium wrappers ship in a later milestone).
- `BotPool` for multi-bot orchestration (architecture is ready,
  not yet exposed).
- Rust mirror (milestone 003).
- PyO3 bridge (separate later milestone).
