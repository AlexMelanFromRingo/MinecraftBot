# Research: Full Bot Parity Across Three Backends

**Phase**: 0 — Outline & Research
**Feature**: [spec.md](./spec.md)
**Plan**: [plan.md](./plan.md)
**Date**: 2026-05-13

This document records the technical decisions that resolve the spec's clarifications and the open questions that surfaced while drafting the plan. Each decision lists rationale and alternatives weighed.

---

## R-1: Sync property bridge from Rust `async fn` to Python attribute

**Decision**: Accel `#[pymethods]` declares each accessor as `#[getter]` and inside the wrapper, drive the Rust `async fn` to completion via the existing tokio runtime handle stored on the `Bot` `#[pyclass]`. Use `tokio::runtime::Handle::block_on` on a borrowed handle (not `Runtime::new()` per call). For methods that may take significant time (most accessors do not — they touch in-memory state behind an `Arc<RwLock<BotState>>`), the wrapper still releases the GIL via `py.allow_threads(|| handle.block_on(rust_async_call))` so other Python threads keep running.

**Rationale**: From Q1 in the spec — Python user scripts read `bot.x` as an attribute today, and the import-swap promise (US1) breaks if accel forces `await bot.x()`. The only sustainable bridge is a sync property wrapper. The pure-Rust API stays `async fn` because tokio embedders prefer async-everywhere.

**Alternatives considered**:
- `block_on` inside the async runtime context — panics on tokio "blocking from within async". Mitigated by `py.allow_threads`, which moves execution off the asyncio thread; verified in 003's existing `walk_to` bridge.
- Cache the value in a `RwLock` and return without blocking — does not work for fields that are network-derived (e.g., `entity_id` arrives at login).
- Make Python `Bot` a coroutine-everywhere class with `bot.x` being a Python descriptor that returns the cached value — works but adds a sync-shadow field that may drift.

---

## R-2: Per-method scope of `tokio::sync::Mutex` for serialisation

**Decision**: One `tokio::sync::Mutex` per Bot for **inventory-mutating** methods (click_slot, move_item, quick_move, equip_armor, unequip_armor, swap_to_offhand, drop_item, craft, open_*, close_container). Movement, accessors, world queries, observation, look/jump/sneak/sprint, attack, swing_arm, say do **not** acquire this mutex.

**Rationale**: Python uses a per-`action_slot` `asyncio.Lock` for inventory mutations (matches the `async with guard(self.action_slot)` lines in `bot.py`). Without serialisation, two concurrent `move_item` calls would interleave click sequences and corrupt the inventory state on the server side. Movement and queries are read-only or already serialised by the physics tick loop.

**Alternatives considered**:
- Single global mutex — over-serialises (a `look_at` would block a parallel `move_item`).
- Per-method mutex — wrong granularity; the conflict is between any two inventory mutations, not within one method type.
- Lock-free via atomic state-id — Mojang's protocol still requires sequential clicks per window; lock-free does not help here.

---

## R-3: `look_at` numerical precision parity

**Decision**: Use f64 throughout the calculation in Rust and serialise as f32 only at the packet boundary (the wire protocol uses f32 for yaw/pitch). This matches the Python reference which uses Python floats (= f64) and converts to f32 at packet build. Tolerance in parity test: `abs(yaw_rust - yaw_py) < 0.01°` and same for pitch. The test normalises across the f32 quantisation step (~0.0055° at 1 sin/cos quanta).

**Rationale**: Python's float-then-f32 chain has a known quantisation pattern. Matching it byte-for-byte requires the same chain. Since both backends use f64 internally and serialise via the same `Float.into_bytes()` path, parity is automatic; the tolerance only handles compiler-level f64 differences (which empirically are < 1 ULP).

**Alternatives considered**:
- All-f32 in Rust — loses precision in `atan2` when bot is far from world origin (large coordinate values lose mantissa bits).
- All-f64 including packet — wrong protocol shape; server rejects.

---

## R-4: `dig` break-time table and parity tolerance

**Decision**: Rust loads `protocol-data/v763/block_states.json` once at startup and computes break-time in ticks via:

```
hardness = block.hardness
factor = if held_tool_can_harvest { 1.5 / tool_speed } else { 5.0 / hand_speed }
ticks = (hardness * factor * 20.0).ceil() as i32
```

with the same constants the Python reference uses. The whitelist in Q4 covers the `finish_break` packet's tick offset with ±1 tolerance for f64 ULP drift.

**Rationale**: From Q4 — exact byte equality is fragile across compilers. The tolerance is narrow (one packet, one field, ±1 tick) and any wider drift fails the test.

**Alternatives considered**:
- Integer arithmetic (multiply hardness×100, integer ceil) — would give exact equality but requires changing Python first, which violates Constitution I.
- No tolerance — fails on tier-0 stone in some CI environments (observed empirically in 003).

---

## R-5: Behaviour-tree `async fn` trait dispatch

**Decision**: Use `async-trait` 0.1 as a Cargo dependency. The `Leaf` trait becomes:

```rust
#[async_trait]
pub trait Leaf: Send + Sync {
    async fn tick(&mut self, bot: &Bot, ctx: &BehaviourCtx) -> NodeStatus;
    fn reset(&mut self) {}
}
```

This produces `Pin<Box<dyn Future + Send>>` returns under the hood, which is the only way to put async-trait objects into a `Vec<Box<dyn Leaf>>` (children of a Selector/Sequencer).

**Rationale**: Without `async-trait`, the trait must be hand-rolled with a `BoxFuture` return type, which is ergonomically painful and easy to get wrong (Send bounds, lifetime parameters). The dep is small (~30 lines of proc-macro expansion per impl), used by tokio internally, and does not leak into the public API of `minecraft_bot` (Cargo.toml dep, not a re-export). Constitution VI ("zero runtime deps in the **Python core**") explicitly scopes the constraint to Python; Rust core was always allowed minimal deps (tokio, bytes, flate2, thiserror, serde, parking_lot, plus this).

**Alternatives considered**:
- Manual `BoxFuture` return — 4 extra lines of boilerplate per leaf; rejected for cost/benefit.
- Sync `tick` returning `NodeStatus` and the runner polls a separate `Future` field — breaks composition (a Selector cannot await a child cleanly).
- `tokio::macros` `async_recursion` — wrong tool; that's for recursive async functions, not trait dispatch.

---

## R-6: `BehaviourCtx` <-> Python dict conversion strategy

**Decision**: Conversion happens on **entry** and **exit** of `PyLeaf::tick`. On entry, the Rust `BehaviourCtx` is rendered into a Python `dict` via a per-variant match (Int->int, Float->float, Bool->bool, String->str, Bytes->bytes, Json(Value)->recursive convert). The Python user's coroutine receives this dict, mutates it freely, and the wrapper converts back. Non-primitive Python values (objects, lambdas) round-trip through `BehaviourValue::Json(serde_json::Value)` if they are JSON-serialisable; otherwise the wrapper raises `TypeError` at exit time pointing to the offending key.

**Rationale**: Python users expect to do `ctx["found_food"] = True; ctx["target_pos"] = (x, y, z)` without ceremony. Converting per call is O(N) in ctx size, which is small (typical BT has <20 keys). Avoiding the conversion by holding a `Py<PyDict>` across `await` points would require GIL re-acquisition on every tokio task switch, which is slow.

**Alternatives considered**:
- Hold a `Py<PyDict>` across awaits — heavy GIL contention, hard to reason about.
- Restrict ctx to a fixed schema — undermines flexibility users expect from Python BT.
- Use `pyo3::types::IntoPyDict` and skip the value-enum entirely — couples pure-Rust to pyo3, violates R-3 (no pyo3 in pure-Rust core).

---

## R-7: Inventory state — dual list + transactional click sequence

**Decision**: `InventoryState` holds `player_slots: [Option<ItemSlot>; 46]`, `container_slots: Vec<Option<ItemSlot>>`, `cursor: Option<ItemSlot>`, `window_id: u8`, `state_id: i32`, `next_transaction_id: AtomicI32`. State updates on three packet kinds:

- `SetSlot` -> patch single slot based on `window_id + slot_index`.
- `WindowItems` -> rewrite container_slots wholesale (and if window_id=0, the player slots too — server can override).
- `SetCarriedItem` -> update `held_slot` field on BotState (not InventoryState directly).

Each `click_slot` call increments `next_transaction_id`, sends `ServerboundClickWindow`, optimistically updates the local state (mirroring Python), and waits for the server's `WindowConfirmation` packet matching the transaction id (5s timeout). Mismatch -> rollback to pre-click state and return error.

**Rationale**: From Q5 — dual-list is correct. The transaction id ↔ confirmation handshake is mandatory; without it, the local state diverges from the server's (Mojang specifically designed this to detect anti-cheat clients). Python already does this in `inventory_click.py`.

**Alternatives considered**:
- No optimistic update, wait for confirmation first — simple, but every move_item becomes serialised by the network round-trip (latency >50ms).
- Pessimistic mutex over the whole inventory while waiting — same problem.
- Skip transaction_id confirmation — fails Paper's anti-cheat after ~30 clicks.

---

## R-8: Open-container handshake

**Decision**: `open_block_container(x, y, z, kind)` performs:

1. `look_at(x + 0.5, y + 0.5, z + 0.5)` to orient toward the block.
2. Send `ServerboundUseItemOn` with that block's face (closest face from bot's position).
3. Subscribe to `OpenScreen` via the existing packet-hook mechanism with a `tokio::sync::oneshot` channel.
4. Wait up to 5 seconds for an `OpenScreen` packet whose `kind` matches the request.
5. On success: store `window_id`, emit `WindowItems` listener to populate `container_slots`, return `window_id`.
6. On timeout: send `ServerboundCloseWindow(0)` for safety, return `Err(ContainerOpenError::Timeout)`.

**Rationale**: This is exactly Python's flow. The hook-based approach reuses the 003 packet-hook subscription primitive.

**Alternatives considered**:
- Poll for `OpenScreen` via state read — race condition.
- Single hook that captures every `OpenScreen` — works but adds global state.

---

## R-9: `craft` recipe matching against `protocol-data/v763/recipes.json`

**Decision**: At Rust crate startup, `recipes.rs` loads the JSON and indexes recipes by a normalised key: a hash of the 9-cell grid (item-id strings with `None` -> "", row-major). `craft(recipe, x, y, z, *, repeat, timeout)` looks up the recipe id, then plays the canonical click sequence (Python's algorithm: pick up each ingredient, place into the 3x3 crafting slot, take output, repeat). The recipe-id lookup matches Python's strategy.

**Rationale**: The protocol-data file already exists. Indexing once at startup is O(N) recipes; lookups become O(1). Python's algorithm is already verified.

**Alternatives considered**:
- No pre-index, linear scan per craft — O(N) per call, N~500 recipes; acceptable but wasteful.
- Server-side recipe-book click (`PlayerClickRecipe` packet) — simpler protocol-wise, but Python does not use it and parity requires same packet sequence.

---

## R-10: Live-test infrastructure for Rust `cargo test --features live-smoke`

**Decision**: New file `tests/rust/integration_bot_full.rs` opens a connection to Paper at `172.26.160.1:25565` (configurable via `MC_BOT_TEST_SERVER` env var) using one of `TestBot1..9` from the test arena's op list. Each method has a `#[tokio::test]` that connects, runs the method, asserts post-condition, disconnects. Runs only under `--features live-smoke` (carry-over from 003). Each test gets its own bot username (cycle through `TestBot1`..`TestBot9`) to avoid duplicate-login conflicts when tests run in parallel — but the suite still defaults to single-threaded (`--test-threads=1`) to keep server load predictable.

**Rationale**: Constitution V (live testing mandatory). Reusing 003's pattern reduces new infra. Sequential by default avoids the multi-bot-on-the-same-name pitfall.

**Alternatives considered**:
- Mock server in Rust — forbidden by Constitution V.
- Run against a fresh `cargo test`-spawned Paper container — heavy CI cost and needs a Java runtime; the live arena is already running.

---

## R-11: Parity test discovery — introspection vs explicit table

**Decision**: `test_bot_full_parity.py` uses `inspect.getmembers(Bot, predicate=inspect.isfunction)` on the Python `Bot` class, filters to public names (no leading underscore), subtracts the `PYTHON_ONLY_METHODS` allow-list, and asserts every remaining name exists on `minecraft_bot_accel.Bot` as either a method or a `#[getter]` property. Signatures are compared shape-only (parameter count, parameter names if Python has them, return type via PEP 484 annotation when both sides have one).

**Rationale**: Self-updating test. When someone adds `bot.dance()` to Python, the test fails until accel implements it (or it's added to `PYTHON_ONLY_METHODS` with a comment).

**Alternatives considered**:
- Hardcoded list of methods in the test — drifts; defeats the purpose.
- Compile-time check in accel via `#[allow(non_snake_case)]` macro — works but needs macro authoring effort.

---

## R-12: Performance gates for newly-ported world queries

**Decision**: `tests/python/perf/test_speedup_world_query.py` adds three gates: `find_blocks_nearby` (search for stone in a 32-block radius from a pre-loaded chunk fixture) >=3x, `raycast` (32-block straight ray through a wall) >=3x, `scan_volume` (radius=8 cube around bot) >=3x. Pre-loaded chunk fixture comes from existing `tests/python/fixtures/chunk_*.bin`.

**Rationale**: From SC-004. 3x is a conservative bar that still validates the native-speed claim. The pathfinder gate stays at 4.5x (set by 003).

**Alternatives considered**:
- 5x — too aggressive for `raycast` which is already O(distance), gain is from saving Python interpreter overhead per DDA step (~2-3x).
- No gates, only correctness tests — loses the perf-regression guard.

---

## Open items deferred to implementation phase

- Whether to vendor a hardness table separately or compute on-demand from `block_states.json` — depends on file size at runtime; check during T-implementation.
- Whether `iter_accessible_slots` returns a Rust iterator (`impl Iterator`) or a `Vec<(usize, Option<ItemSlot>)>` — likely `impl Iterator` for zero-alloc, fall back to `Vec` if pyo3 binding gets awkward.
- Behaviour-tree `BehaviourRunner::run` cancellation semantics — Python uses `asyncio.CancelledError`; Rust uses `tokio::select!` with a cancel signal. Implement minimal cancel via `tokio::sync::Notify` first.

These are tactical and do not block planning.
