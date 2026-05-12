# Phase 1 Data Model: Native-side entities & FFI shapes

**Feature**: 003-rust-pyo3-bridge
**Date**: 2026-05-12

## Overview

This document describes the native-side data shapes for
`minecraft_bot_accel`. Three categories:

1. **Owned Rust state** — lives in the `minecraft_bot` Rust crate
   (`rust/`), no PyO3 attributes. Cross-crate consumers can use it
   directly.
2. **PyO3 facade types** — `#[pyclass]` wrappers in `python-ext/src/`.
   Most are thin handles to (1).
3. **Plain Python-shaped output values** — `#[pyclass]` value types
   with `get_all` field access. These mirror the Python reference's
   frozen dataclasses field-for-field.

For every dataclass in `python/minecraft_bot/`, there is a parallel
Rust struct + pyclass in 003. The table below enumerates them.

## Parity Table: Python dataclass ↔ Rust struct ↔ PyO3 class

Field-level parity is asserted by automated tests in
`tests/python/parity/test_field_parity.py` (introspects `__dataclass_fields__`
of Python and `__dict__` of pyclass; demands set equality).

| Python (`minecraft_bot.*`) | Rust (`minecraft_bot::*`) | PyO3 (`minecraft_bot_accel.*`) | Fields (parity-checked) |
|---|---|---|---|
| `bot.Bot` | `bot::Bot` | `bot::PyBot` exposed as `Bot` | `connection`, `world`, `inventory`, `effects`, `position`, `health`, `food`, `yaw`, `pitch`, `on_ground`, `wire_log` |
| `connection.Connection` | `connection::Connection` (extended) | `connection::PyConnection` as `Connection` | `host`, `port`, `username`, `state`, `is_connected`, `protocol_version`, `wire_log` |
| `world.cache.WorldCache` | `world::cache::WorldCache` | `world::PyWorld` as `World` | (opaque; access via methods) |
| `world.chunk.Chunk` | `world::chunk::Chunk` | `world::PyChunk` as `Chunk` | `cx`, `cz`, `min_y`, `section_count`, `sections` |
| `world.chunk.ChunkSection` | `world::chunk::ChunkSection` | `world::PyChunkSection` as `ChunkSection` | `block_states`, `biomes`, `block_light`, `sky_light`, `non_air_count` |
| `world.block_table.Block` | `world::block_table::Block` | `world::PyBlock` as `Block` | `id`, `name`, `material`, `is_solid`, `is_water` |
| `observation.Observation` | `observation::Observation` | `observation::PyObservation` as `Observation` | `tick`, `position`, `yaw`, `pitch`, `on_ground`, `health`, `food`, `saturation`, `effects`, `inventory`, `nearby_blocks`, `nearby_entities` |
| `observation.Vec3` | `observation::Vec3` | `observation::PyVec3` as `Vec3` | `x`, `y`, `z` |
| `slots.ItemStack` | `slots::ItemStack` | `slots::PyItemStack` as `ItemStack` | `item_id`, `count`, `nbt` |
| `entities.Entity` | `entities::Entity` | `entities::PyEntity` as `Entity` | `entity_id`, `uuid`, `kind`, `position`, `yaw`, `pitch`, `velocity`, `metadata` |
| `status_effects.StatusEffect` | `effects::StatusEffect` | `effects::PyStatusEffect` as `StatusEffect` | `id`, `amplifier`, `duration_ticks`, `ambient`, `show_particles` |
| `pathfinding.Path` | `pathfinding::Path` | `pathfinding::PyPath` as `Path` | `steps`, `cost`, `node_count` |
| `physics.PhysicsState` | `physics::State` | `physics::PyPhysicsState` as `PhysicsState` | `position`, `velocity`, `on_ground`, `in_water`, `in_lava` |
| `wire_log.WireLog` | `wire_log::WireLog` (existing) | `wire_log::PyWireLog` as `WireLog` | `path`, `mode`, `entries_written` |
| `codec.Reader` | `codec::Reader` (existing) | `codec::PyReader` as `Reader` | `pos`, `remaining` |
| `codec.Writer` | `codec::Writer` (existing) | `codec::PyWriter` as `Writer` | `bytes_written` |

## Submodule mirroring rules

The `minecraft_bot_accel.*` namespace mirrors `minecraft_bot.*`
1-for-1 at the public level. Specifically:

- `minecraft_bot_accel.codec.varint` exposes `read(buf, offset) → (value, n)`
  and `write(value) → bytes` matching `minecraft_bot.codec.varint`.
- `minecraft_bot_accel.codec.varlong`, `nbt`, `bitset`, `slot`, …:
  same pattern.
- `minecraft_bot_accel.framer.Framer`: same pattern.
- `minecraft_bot_accel.protocol.v763.packets.play.*`: every packet
  module from the Python reference has a matching one here, exposing
  `encode(pkt, writer)`, `decode(reader) → pkt`, and the packet's
  dataclass type.

Implementation: the `#[pymodule]` root macro builds a tree of
`PyModule::new` children matching the Python layout. A single
top-level function in `python-ext/src/lib.rs` is the registration
glue; one entry per top-level subpackage.

## Async-bridge state machine

```
Python side                    Bridge                    Rust side
-----------                    ------                    ---------
await bot.connect()
    │
    ├─► future_into_py ───►  spawn tokio task ───► Connection::connect
    │                         (cross-registered                 │
    │                          asyncio loop +                   ▼
    │                          tokio runtime)              ┌─────────────┐
    │                                                       │ tcp connect │
    │       Python yields to loop                          │ handshake   │
    │                                                       │ login start │
    │                                                       └─────────────┘
    │                                                              │
    │       call_soon_threadsafe(set_result(ok))  ◄─────────  task.complete
    │                                                              │
    ▼
returns Bot instance with state=PLAY
```

Cancellation flow:

```
asyncio.CancelledError raised on the awaitable
    │
    ▼
pyo3-async-runtimes drops the Future → tokio task aborts (cooperative
    cancel via the bridge's `cancel_on_drop` handle)
    │
    ▼
Connection state machine sees the abort, sends graceful disconnect
    if state >= PLAY, otherwise just drops the socket
```

## State transitions: Connection lifecycle (Rust + Python parity)

```
INIT ──connect()──► HANDSHAKE ──intent=login──► LOGIN
                                                    │
                                                    │ login_success
                                                    ▼
                                            CONFIGURATION ──finish_config──► PLAY
                                                    │                          │
                                                    │                          │ disconnect(reason)
                                                    │                          ▼
                                                    │                       CLOSED
                                                    │
                                                    │ kick / network error
                                                    ▼
                                                 CLOSED
```

Both implementations MUST drive this state machine identically. A
parity test in `tests/python/parity/test_connection_state.py` runs a
canned 5-second login session and asserts state transitions
matched event-for-event between the two backends.

## Validation rules (carried over from 002)

- **Position send guard**: the Bot MUST NOT send a Player Position
  packet whose distance from the last server-known position exceeds
  5.0 blocks (anti-cheat cap). Enforced in `behaviour::walk_to`
  module on the Rust side.
- **Chunk cache invariant**: `cache.get_chunk(cx, cz)` returns
  `Some(c)` iff a `chunk_data_and_light` packet with that key has
  been received and not unloaded.
- **Inventory state**: window-click flow waits for `confirm_transaction`
  before considering the action committed.

## Cross-package serialisation contract

Both backends MUST emit identical JSONL into WireLog (R-009). A
single dump-comparison test confirms this on every CI run.

For Observation snapshots, both backends MUST produce dict equality
under `Observation.to_dict()`:

```python
o_py = bot_py.observation()
o_acc = bot_acc.observation()
assert o_py.to_dict() == o_acc.to_dict()  # field-by-field
```

`to_dict` performs a deep, type-coerced render (Vec3 → tuple,
Optional → None, etc.). This is the parity gate for the
observation surface.

## Hooks and event subscriptions (Principle III)

Both backends expose:

- `bot.on_packet(name, fn)` — register handler for a named packet.
- `bot.pre_tick(fn)` / `bot.post_tick(fn)` — physics tick hooks.
- `bot.on_event(event_name, fn)` — generic event bus.

In the native backend, hook callbacks are stored as `PyObject` and
invoked from the appropriate Rust async/sync context with the GIL
acquired. `py.allow_threads` is NOT used inside hook dispatch
sections — the Python user's callback owns control flow.

## Cross-implementation runtime interop (allowed and forbidden)

**Allowed**:
- Running two `Bot` instances — one from each backend — in the same
  process, against the same or different servers. (Each owns its
  own tokio runtime if multi-runtime is configured; default is a
  shared tokio runtime.)
- Comparing `to_dict()` outputs between backends in tests.
- Reading a `minecraft_bot` WireLog from a `minecraft_bot_accel`
  replay tool (because the file format is byte-identical, R-009).

**Forbidden** (will not be supported in 003):
- Passing a `minecraft_bot.Observation` instance to
  `minecraft_bot_accel.Bot.set_observation(...)`. Types are distinct;
  caller must use `to_dict()` / `from_dict()` to round-trip.
- Importing types from one backend into the other's module tree.
- Shared mutable state (e.g., a single `WorldCache` used by both
  backends).
