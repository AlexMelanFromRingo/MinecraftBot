# Migrating a 002-era bot script to `minecraft_bot_accel`

This guide walks through swapping the Python reference for the native
PyO3 façade. The goal is **identical observable behaviour at higher
speed** with a single-line code change.

## Install the native package

```bash
# Dev (build from source):
maturin develop --manifest-path python-ext/Cargo.toml

# Release (once wheels are published):
pip install minecraft_bot_accel
```

The native package is **separate** from `minecraft_bot`. Both can be
installed side-by-side; importing one does NOT import the other.

## Swap the import

**Before** (Python reference, 002):

```python
from minecraft_bot.bot import Bot

async def main():
    async with Bot.offline("host", 25565, "Greeter") as bot:
        await bot.walk_to(x + 5, y, z)
```

**After** (PyO3 façade, 003):

```python
import minecraft_bot_accel as mb

async def main():
    bot = mb.Bot.offline("host", 25565, "Greeter")
    await bot.connect()
    try:
        pos = await bot.position()
        await bot.walk_to(pos[0] + 5, pos[1], pos[2])
    finally:
        await bot.disconnect()
```

That's the entire migration. The async surface, the property names,
and the return types are identical.

## What's different (right now)

The accel façade is **growing** the Python reference's surface
incrementally. As of 003 it exposes:

- `Bot.offline(host, port, username) -> Bot`
- `await bot.connect()`, `await bot.disconnect()`
- `await bot.position()` -> `(x, y, z, yaw, pitch)` or `None`
- `await bot.entity_id()`, `await bot.health()`, `await bot.food()`
- `await bot.walk_to(x, y, z, *, timeout=30.0)`
- `await bot.walk_to_blind(x, y, z, *, timeout=30.0)` (diagnostic)
- `await bot.drop_held_item(*, full_stack=False)`
- `await bot.send_raw(payload: bytes)` (raw packet escape hatch)
- `bot.loaded_chunk_count()` (sync)
- `bot.world` -> `World` view (sync)
  - `world.get_block_id`, `get_block_name`, `is_solid`, `is_water`
  - `world.find_blocks_nearby(name, origin, *, radius, limit)`
  - `world.apply_block_change`, `apply_map_chunk`, `apply_unload_chunk`
  - `world.dimension`, `min_y`, `section_count`
- `minecraft_bot_accel.codec.{Reader, Writer}`
- `minecraft_bot_accel.codec.varint.{read, write, encoded_size,
   read_many, write_many}`
- `minecraft_bot_accel.codec.varlong.{read, write}`
- `minecraft_bot_accel.codec.nbt.{read, read_bytes, write,
   TAG_BYTE..TAG_LONG_ARRAY}`
- `minecraft_bot_accel.framer.Framer`
- `minecraft_bot_accel.pathfinding.find_path(world, start, goal, ...)`
- `minecraft_bot_accel.physics.{tick, tick_n, PhysicsState, PhysicsIntent}`
- `minecraft_bot_accel.observation.{Vec3, Observation}`
- `minecraft_bot_accel.entities.Entity`
- `minecraft_bot_accel.effects.{StatusEffect, effect_name, effect_id}`
- `minecraft_bot_accel.ItemStack`
- `minecraft_bot_accel.errors.*` (full exception hierarchy: 23 classes)
- `minecraft_bot_accel.WireLog`
- `await bot.on_packet(packet_id, callback)` plus `await bot.clear_hooks()`
- `await bot.walk_to_blind(...)` diagnostic mode

Surface still landing in later phases:
- Live `bot.inventory` tracker mirroring the Python WindowItems flow
- Live `bot.entities` nearby-entity tracker
- Chat / behaviour trees / dig

## Performance profile

Measured 2026-05-12 on Linux x86_64 WSL2, Python 3.12.3, Rust 1.94.0,
release build via maturin.

| Operation | Python | Accel | Speedup |
|---|---|---|---|
| End-to-end chunk burst (decode + cache + find_blocks) | 0.218 s | 0.007 s | **31.44×** |
| Chunk decode alone (48 KiB payload) | 345 µs | 121 µs | **2.84×** |
| VarInt batched read (N=1000 per call) | 112 ms | 4 ms | **26.82×** |
| VarInt batched write (N=1000 per call) | 76 ms | 3 ms | **24.68×** |
| NBT decode (638 B real heightmaps) | 13 ms | 4 ms | **3.26×** |
| Physics tick (batched, N=50 per call) | 49 ms | 6 ms | **8.38×** |
| A* pathfinder (30 random pairs on 32×32 grid) | 79 ms | 12 ms | **6.38×** |
| VarInt single read (per-call) | 747 ns | 2095 ns | 0.36× (FFI dominates) |
| VarInt single write (per-call) | 671 ns | 2442 ns | 0.27× (FFI dominates) |

Heavy operations and batched primitives win big. Per-op codec calls
on 1-2 byte values cross the FFI boundary every call and lose to
pure Python. Use the batched APIs (`varint.read_many`,
`varint.write_many`, `physics.tick_n`) when you have many values to
process at once. Bot.walk_to and Bot.dispatcher already amortise
the boundary internally so callers do not have to think about it.

## Two implementations in one process

You can hold instances of both backends at the same time:

```python
import minecraft_bot
import minecraft_bot_accel as mb

bot_py = minecraft_bot.bot.Bot.offline(...)
bot_ac = mb.Bot.offline(...)
```

They don't share state. Public types are **structurally identical
but not type-identical**:

```python
isinstance(o, minecraft_bot.Observation)         # works on py-bot return
isinstance(o, minecraft_bot_accel.Observation)   # works on ac-bot return
# Cross-package isinstance returns False - by design (Constitution VI).
```

Compare by **content** (`.to_dict()` / field-by-field) in parity
tests; never by `isinstance` across packages.

## Verify your migration

After switching:

```bash
# Run your existing test suite against accel:
pytest --backend accel

# Or use the parity harness from this repo:
pytest tests/python/parity -m "not live"

# Live integration:
pytest tests/python/parity -m live
```

If any test fails against accel but passes against python, the
behaviour gap is a parity bug - please file an issue with the
fixture / live capture.
