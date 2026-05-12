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
- `await bot.drop_held_item(*, full_stack=False)`
- `bot.loaded_chunk_count()` (sync)
- `bot.world` -> `World` view (sync)
  - `world.get_block_id`, `get_block_name`, `is_solid`, `is_water`
  - `world.find_blocks_nearby(name, origin, *, radius, limit)`
  - `world.apply_block_change`, `apply_map_chunk`, `apply_unload_chunk`
  - `world.dimension`, `min_y`, `section_count`
- `minecraft_bot_accel.codec.{Reader, Writer, varint, varlong}`
- `minecraft_bot_accel.framer.Framer`
- `minecraft_bot_accel.pathfinding.find_path(world, start, goal, ...)`
- `minecraft_bot_accel.physics.{tick, PhysicsState, PhysicsIntent}`
- `minecraft_bot_accel.errors.*` — full exception hierarchy
- `minecraft_bot_accel.WireLog`

Surface still landing in later phases:
- Inventory item tracker (`bot.inventory`)
- Entity tracker (`bot.entities`)
- Observation snapshot (`bot.observation()`)
- Chat / behaviour trees / dig

## Performance profile

| Operation | Python | Accel | Speedup |
|---|---|---|---|
| Chunk decode (48 KiB payload) | 345 µs | 121 µs | **2.84×** |
| VarInt write (1-2 bytes) | 671 ns | 2442 ns | 0.27× (FFI dominates) |
| VarInt read | 747 ns | 2095 ns | 0.36× (FFI dominates) |

**Takeaway**: heavy operations (chunk decode, pathfinding, physics)
win big. Per-op codec calls cross the FFI boundary and lose to pure
Python on tiny ops. The accel package is most valuable when used at
**packet / chunk / pathfinding** granularity — exactly the granularity
the Python reference's hot loops operate at.

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
# Cross-package isinstance returns False — by design (Constitution VI).
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
behaviour gap is a parity bug — please file an issue with the
fixture / live capture.
