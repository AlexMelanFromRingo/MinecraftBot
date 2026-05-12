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
| `003-rust-pyo3-bridge` | Rust port of 002 bot-API + PyO3 façade (`minecraft_bot_accel`): World cache, A* pathfinder, 20Hz physics, async Connection dispatcher, Bot facade with `connect`/`walk_to`/`drop_held_item`/`position`/`world`. Live-validated on Paper 1.20.1. Chunk decode 2.84× faster than pure Python. abi3 wheel matrix for 5 platforms. | In progress (54%) |

See:
- **Two-implementation overview** (003): [`specs/003-rust-pyo3-bridge/plan.md`](./specs/003-rust-pyo3-bridge/plan.md), [`specs/003-rust-pyo3-bridge/quickstart.md`](./specs/003-rust-pyo3-bridge/quickstart.md)
- **Bot API plan** (002): [`specs/002-bot-api/plan.md`](./specs/002-bot-api/plan.md)
- **Bot API quickstart** (002): [`specs/002-bot-api/quickstart.md`](./specs/002-bot-api/quickstart.md)
- **Protocol foundation spec** (001): [`specs/001-protocol-foundation/spec.md`](./specs/001-protocol-foundation/spec.md)
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

### Native-speed alternative (003)

The same script runs against the PyO3 façade with one import edit:

```python
import asyncio
import minecraft_bot_accel as mb  # instead of `from minecraft_bot.bot import Bot`

async def main() -> None:
    bot = mb.Bot.offline("172.26.160.1", 25565, "Greeter")
    await bot.connect()
    try:
        await bot.walk_to(bot.world.dimension and 10005, 200, 10005, timeout=15.0)
        # Inspect via the native World cache (loaded by the packet
        # dispatcher in Rust — no Python in the hot path):
        print("loaded chunks:", bot.loaded_chunk_count())
        print("block under feet:", bot.world.get_block_name(*[int(c) for c in (await bot.position())[:3]]))
    finally:
        await bot.disconnect()

asyncio.run(main())
```

Build the native package from source with `maturin develop --manifest-path python-ext/Cargo.toml`. Pre-built wheels for Linux x86_64/aarch64, macOS arm64/x86_64, and Windows x86_64 land on GitHub Releases once a `v*` tag is pushed.

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
