# MinecraftBot

A bot/agent framework for Minecraft Java Edition (1.20.1, protocol 763).
Python is the canonical reference implementation; Rust mirrors it for
performance, with a future PyO3 bridge that subsumes the Python core
while preserving its API surface.

## Status

| Milestone | Description | State |
|-----------|-------------|-------|
| `001-protocol-foundation` | Codec + framer + 176-packet registry + Connection lifecycle + WireLog | Complete |
| `002-bot-api` | High-level Bot: walk_to, A*+physics, world cache, entity tracker, inventory + containers, dig, auto-eat, follow, behaviour trees, chat, AI observation API | Complete (89/92) |

See:
- **Bot API plan**: [`specs/002-bot-api/plan.md`](./specs/002-bot-api/plan.md)
- **Bot API quickstart**: [`specs/002-bot-api/quickstart.md`](./specs/002-bot-api/quickstart.md)
- **Protocol foundation spec**: [`specs/001-protocol-foundation/spec.md`](./specs/001-protocol-foundation/spec.md)
- **Project constitution**: [`.specify/memory/constitution.md`](./.specify/memory/constitution.md)

## Hello, bot

```python
import asyncio
from minecraft_bot.bot import Bot

async def main() -> None:
    async with Bot.offline("172.26.160.1", 25565, "Greeter") as bot:
        await bot.say("Hello, world!")
        await bot.walk_to(bot.x + 5, bot.y, bot.z, timeout=30.0)

asyncio.run(main())
```

A 10-line behaviour-tree variant:

```python
from minecraft_bot.behaviour import Selector, WalkTo, EatWhenHungry, BehaviourRunner

tree = Selector([
    EatWhenHungry(threshold=15),
    WalkTo(0, 64, 0, timeout=30.0),
])
async with Bot.offline("172.26.160.1", 25565, "BTBot") as bot:
    await BehaviourRunner(tick_dt=0.5).run(tree, bot, max_ticks=200)
```

## Quick start

```bash
# Python (canonical) — 002 Bot API
pip install -e python/[dev]
pytest -q tests/python/unit              # ~930 offline unit tests
pytest -m live tests/python/integration  # 24 live integration tests
pytest -m "live and slow"                # 60-second uptime smoke

# Rust (mirror, 001 only)
cargo build --manifest-path rust/Cargo.toml
cargo test --manifest-path rust/Cargo.toml
cargo test --manifest-path rust/Cargo.toml --features live-smoke
```

End-to-end usage examples:
- `specs/001-protocol-foundation/quickstart.md` (low-level Connection)
- `specs/002-bot-api/quickstart.md` (high-level Bot)
- `tools/quickstart_us*.py` (one runnable script per user story)

## Bot API at a glance

```text
bot.walk_to(x, y, z)        # A* + physics + anti-cheat-safe sending
bot.follow(eid)             # track moving entity
bot.dig(x, y, z, tool=...)  # break-time aware
bot.attack(eid)             # use_entity + arm swing
bot.auto_eat(threshold=15)  # background hunger watcher
bot.open_chest(x, y, z)     # also open_furnace / open_barrel / etc.
bot.smelt(input, fuel, ...) # full furnace recipe

# AI observation API
bot.raycast()               # first solid block along look direction
bot.scan_volume(radius=8)   # all blocks in a Chebyshev cube
bot.voxel_grid(radius=4)    # 3-D grid of state IDs (ML-ready)
bot.world_map_3d(radius_xz=16, radius_y=8)   # larger box
bot.chunks_around(radius_chunks=2)            # raw chunks for direct use
bot.observation()           # composite: pose + look hit + voxels + entities
bot.snapshot()              # frozen, picklable full state
```

## Repository layout

```text
python/minecraft_bot/    # Canonical Python implementation
rust/                    # Parity Rust crate
protocol-data/v763/      # Pinned PrismarineJS minecraft-data + golden fixtures
tests/{python,rust}/     # Unit, integration, replay, perf tiers
tools/                   # Codegen, capture, cross-check scripts (not shipped)
specs/                   # Spec Kit deliverables
.specify/memory/         # Project constitution
```

## Test target

Paper 1.20.1, `online-mode=false`, default address `172.26.160.1:25565`.

## License

MIT.
