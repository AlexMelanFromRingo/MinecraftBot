# MinecraftBot

A bot framework for Minecraft Java Edition 1.20.1 (protocol 763),
shipped as three coordinated artefacts that target three deployment
scenarios.

| Package | Path | Surface | Use it when |
|---|---|---|---|
| `minecraft_bot` | `python/` | **Full** Bot: walk_to, dig, attack, follow, eat, chat, behaviour trees, inventory, containers, observation snapshot, entity tracker, hooks. | Default for development and any script that needs the complete bot API. Zero runtime deps. |
| `minecraft_bot` (Rust crate) | `rust/` | Codec + framer + 176 packets + Connection + World cache + pathfinding + physics + dispatcher + Bot core (connect, walk_to, drop_held_item, send_raw, hooks). | You want to embed the framework in a non-Python binary, or build something on top of the Rust core directly. |
| `minecraft_bot_accel` | `python-ext/` | A PyO3 facade that re-exports the Rust crate's surface as Python types. Currently mirrors the Rust crate's Bot subset, not the full Python Bot. | You want native-speed chunk decode, A* pathfinder, physics tick, etc. and your script uses the subset of bot API the facade exposes. |

The three artefacts share the wire protocol byte-for-byte (verified by
a 3-way cross-check tool on every PR) and share the same World model,
physics model, and pathfinder algorithm. They differ in **scope**:
the Python reference is the most complete; the Rust crate and accel
facade cover the network + core voxel + motion stack and are still
growing toward the full Python Bot surface. See [`docs/migration_to_accel.md`](./docs/migration_to_accel.md)
for the exact accel surface available today.

Live-tested against Paper 1.20.1, offline mode, on the standard test
arena at `172.26.160.1:25565`.

## Status

- **001 protocol-foundation**: 141/141 tasks closed. Codec, framer, all
  176 v763 packets in both Python and Rust, Connection lifecycle,
  WireLog capture+replay.
- **002 bot-api**: 92/92 tasks closed. High-level Bot in Python:
  `walk_to`, A* pathfinder, 20 Hz physics, world cache, entity tracker,
  inventory, containers, dig, auto-eat, follow, behaviour trees, chat,
  observation snapshot.
- **003 rust-pyo3-bridge**: 95/95 tasks closed. Rust port of 002 plus
  PyO3 facade. Bot, World, pathfinder, physics all work end-to-end on
  the live server. Performance gates pass with margin (see below).

Full specs and task lists live under `specs/001-protocol-foundation/`,
`specs/002-bot-api/`, `specs/003-rust-pyo3-bridge/`. The project
constitution is in `.specify/memory/constitution.md`.

## Hello, bot (Python reference)

```python
import asyncio
from minecraft_bot.bot import Bot

async def main():
    async with Bot.offline("172.26.160.1", 25565, "Greeter") as bot:
        await bot.say("hello, world")
        await bot.walk_to(bot.x + 5, bot.y, bot.z, timeout=30.0)

asyncio.run(main())
```

A ten-line behaviour-tree variant:

```python
from minecraft_bot.behaviour import Selector, WalkTo, EatWhenHungry, BehaviourRunner

tree = Selector([
    EatWhenHungry(threshold=15),
    WalkTo(0, 64, 0, timeout=30.0),
])
async with Bot.offline("172.26.160.1", 25565, "BTBot") as bot:
    await BehaviourRunner(tick_dt=0.5).run(tree, bot, max_ticks=200)
```

## Hello, bot (native-backed)

The same script with one import change. The runtime path swaps to Rust
with no other code edits.

```python
import asyncio
import minecraft_bot_accel as mb

async def main():
    bot = mb.Bot.offline("172.26.160.1", 25565, "Greeter")
    await bot.connect()
    try:
        pos = await bot.position()
        await bot.walk_to(pos[0] + 5, pos[1], pos[2])
    finally:
        await bot.disconnect()

asyncio.run(main())
```

## Quick start

```bash
git clone <repo-url> MinecraftBot
cd MinecraftBot
python3 -m venv .venv && source .venv/bin/activate
pip install -e python/[dev]

# Run the existing Python suite (979 unit tests).
pytest tests/python/unit

# Run live integration tests (needs the Paper test server up).
pytest -m live tests/python/integration
```

To build the native package:

```bash
pip install maturin
maturin develop --release --manifest-path python-ext/Cargo.toml

# Verify both backends load.
python -c "
import minecraft_bot, minecraft_bot_accel
print(minecraft_bot.__version__, minecraft_bot_accel.__version__)
print(minecraft_bot.implementation, minecraft_bot_accel.implementation)
"
```

Pre-built abi3 wheels for Linux x86_64/aarch64, macOS arm64/x86_64,
Windows x86_64 land on GitHub Releases when a `v*` tag is pushed.

## Performance profile

Measured 2026-05-12 on Linux x86_64 WSL2, Python 3.12.3, Rust 1.94.0,
maturin develop --release. Numbers from
`tests/python/perf/test_speedup_*.py` and `tools/measure_cpu_speedup.py`.

| Operation | Python | Accel | Speedup |
|---|---|---|---|
| Chunk decode + cache + find_blocks (end-to-end) | 0.218 s | 0.007 s | **31.44×** |
| Chunk decode alone (48 KiB captured payload) | 345 µs | 121 µs | **2.84×** |
| VarInt batched read (N=1000 per call) | 112 ms | 4 ms | **26.82×** |
| VarInt batched write (N=1000 per call) | 76 ms | 3 ms | **24.68×** |
| NBT decode (638 B real heightmaps) | 13 ms | 4 ms | **3.26×** |
| Physics tick (batched, N=50 per call) | 49 ms | 6 ms | **8.38×** |
| A* pathfinder (30 random pairs on 32×32 grid) | 79 ms | 12 ms | **6.38×** |

Per-call codec ops cross the FFI boundary every call and lose to pure
Python on tiny operations. The wins are at batched and heavy-op
granularity. Bot.walk_to and Bot.dispatcher don't have this problem
because they cross the boundary once per high-level operation, not
once per byte.

## Project layout

```
python/minecraft_bot/    Python reference implementation
rust/                    Standalone Rust crate (minecraft_bot)
python-ext/              PyO3 facade (minecraft_bot_accel)
protocol-data/v763/      Auto-generated registries + golden bytes
tests/python/            Python tests (unit, integration, parity, perf)
tools/                   Codegen, measurement, cross-check scripts
.github/workflows/       CI: ci.yml, wheels.yml, release.yml
specs/                   Per-milestone spec/plan/tasks/research artefacts
docs/                    User guides (architecture, migration)
```

## Constitutional invariants

- **Python is the spec of record.** Rust and accel mirror the Python
  reference's observable behaviour. Cross-language byte parity is
  gated by `tools/cross_check.py --accel` (50 Python + 50 Rust + 17
  accel fixtures, zero discrepancies).
- **Zero runtime deps in the Python core.** `python/pyproject.toml`
  declares `dependencies = []`. The accel package is a separate
  distributable; nothing in `minecraft_bot` imports from
  `minecraft_bot_accel`.
- **Live testing is mandatory.** Mock servers are forbidden for
  protocol-level tests. Every Bot API method that touches the network
  ships with a passing integration test against Paper 1.20.1 at
  `172.26.160.1:25565` (offline mode).

Full text in `.specify/memory/constitution.md`.

## Documentation

- [`docs/architecture.md`](./docs/architecture.md). Three-implementation
  layout, async-bridge mechanics, packet dispatcher.
- [`docs/migration_to_accel.md`](./docs/migration_to_accel.md). One-line
  import switch and full accel API surface.
- [`docs/examples.md`](./docs/examples.md). Common bot recipes.
- [`docs/protocol_versions.md`](./docs/protocol_versions.md). How to
  add a new Minecraft protocol number (worked example: 1.20.4).
- [`specs/003-rust-pyo3-bridge/quickstart.md`](./specs/003-rust-pyo3-bridge/quickstart.md). Day-to-day dev workflows.
- [`specs/003-rust-pyo3-bridge/research.md`](./specs/003-rust-pyo3-bridge/research.md). Technical decisions, measured speedups.

## License

MIT. See `LICENSE`.
