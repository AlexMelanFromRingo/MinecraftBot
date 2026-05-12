# Architecture

The framework ships three coordinated artefacts that all speak the
same wire protocol and present the same bot API.

## Three-implementation layout

```
                          ┌──────────────────────────┐
                          │  user script              │
                          │  (asyncio Python)         │
                          └────────────┬─────────────┘
                                       │  import
                ┌──────────────────────┼─────────────────────┐
                │                      │                     │
       ┌────────▼─────────┐  ┌─────────▼─────────┐  ┌────────▼────────┐
       │ minecraft_bot    │  │ minecraft_bot_accel│  │  rust crate     │
       │ (Python ref)     │  │  (PyO3 facade)     │  │ (standalone)    │
       │                  │  │                    │  │                 │
       │ pyproject.toml   │  │ pyproject.toml     │  │ Cargo.toml      │
       │ pure stdlib      │  │ depends-on rust/   │  │ tokio + bytes + │
       │                  │  │ via path           │  │ flate2 + serde  │
       └─────────────────┘   └─────────┬─────────┘  └────────▲────────┘
                                       │ links                │
                                       └──────────────────────┘
```

Each artefact builds and ships independently. Users pick one (or hold
references to two side-by-side); none of the three is mandatory.

## Why three?

- **Python reference** is the development surface. Edits are fast,
  errors carry a stack trace, behaviours are easy to validate against
  a live server. The constitution makes Python the spec of record:
  when Python and Rust disagree, the live-server observation breaks
  the tie, then Python is updated, then Rust catches up.
- **Standalone Rust crate** is the production native framework.
  Embeddable in non-Python programs (a CLI tool, a custom service,
  a long-running daemon). No Python build dependency.
- **PyO3 facade** is the bridge. Users who want the Rust speed without
  rewriting their Python script flip one import line.

## Module mirroring

The Python and Rust trees mirror each other one-for-one at the public
level. `python/minecraft_bot/codec/varint.py` has a sibling
`rust/src/codec/varint.rs` with the same function signatures (modulo
language idiom). All 176 packets at
`python/minecraft_bot/protocol/v763/packets/<state>/<dir>/<name>.py`
have a sibling `.rs` at the same path.

The PyO3 facade does not duplicate the typed dataclass surface. It
exposes the Rust crate's framework types directly as pyclasses:
`Bot`, `World`, `PhysicsState`, `PhysicsIntent`, codec primitives,
errors, WireLog. Users who need typed serverbound packets build them
through the Python reference's encoders and hand the resulting bytes
to `Bot.send_raw(payload)`.

## Async bridge

The standalone Rust crate uses tokio. The PyO3 facade bridges tokio
into Python asyncio via `pyo3-async-runtimes`. The runtime is created
once at module init (`python-ext/src/runtime.rs`), held in a
`OnceLock`, and cross-registered so every `future_into_py(py, async
{...})` returns a Python awaitable that cooperates with the host
asyncio loop.

```
Python asyncio loop  ─────►  pyo3_async_runtimes::tokio
                                       │
                                       ▼
                              tokio runtime (multi-thread)
                                       │
                       ┌───────────────┴─────────────────┐
                       ▼                                 ▼
                Bot::connect                       packet dispatcher
                (login → play)                    (mpsc subscribe loop)
```

## Packet dispatcher

`Connection` runs a play-loop task that decodes inbound packets,
auto-replies to keep-alive and teleport-confirm, and fans out every
packet to a list of `mpsc::UnboundedSender<(packet_id, body)>` subscribers
before the auto-handlers run.

`Bot::connect` subscribes once and routes packet IDs of interest into
the World cache:

| Packet | ID | Action |
|---|---|---|
| map_chunk | 0x24 | decode payload → insert Chunk into World |
| block_change | 0x0A | World.set_block(x, y, z, state_id) |
| multi_block_change | 0x43 | apply each record to the chunk |
| unload_chunk | 0x1E | drop the (cx, cz) entry |
| update_health | 0x57 | bot.state.health/food/saturation |
| synchronize_player_position | 0x3C | bot.state.x/y/z/yaw/pitch (relative + absolute flag bits respected) |

Future packets are added by appending to the match in `bot.rs`.

## World cache

`rust/src/world/cache.rs` owns the chunk hashmap behind a
`parking_lot::RwLock`. Two query paths:

- **Per-call**. `world.get_block_id(x, y, z)` takes the read lock,
  looks up the chunk, returns. Useful for one-off queries.
- **Long-lived guard**. `world.query_guard()` returns a wrapper
  holding the read lock for as long as the guard lives. Used by the
  pathfinder and the batched physics tick; thousands of subsequent
  block queries become plain HashMap reads with no per-call lock
  acquisition. The contention window stays small (one search is
  millisecond-scale).

The same guard pattern lets the PyO3 facade release the GIL during
A* and physics search: the search needs no Python and no per-cell
lock, so it goes under `py.allow_threads(...)` safely.

## Codegen

`tools/generate_rust_packets.py` reads the Python packet definitions
under `python/minecraft_bot/protocol/v763/packets/` and emits the
matching Rust files in `rust/src/protocol/v763/packets/`. Field
types map by table; complex types (NBT, Slot, Chat) go through the
shared codec modules.

Re-run after editing a Python packet definition:

```bash
python tools/generate_rust_packets.py
cargo build --manifest-path rust/Cargo.toml
```

## Cross-language byte parity

`tools/cross_check.py --accel` encodes a fixed test-vector set
through three encoders (Python, standalone Rust, accel) and
asserts all three produce identical bytes. 50 primitive fixtures
in `protocol-data/v763/golden_bytes/primitives.json` plus 17
accel-side codec fixtures.

The CI job `cross-check-all` runs this on every PR touching codec
or packet modules and fails the build on any discrepancy.

## Constitutional invariants enforced by the architecture

- **Zero deps in Python core.** `python/pyproject.toml` declares
  `dependencies = []`. Verified by the install pipeline: `pip install
  -e python/` succeeds in a container with no other packages.
- **Python imports never reach into accel.** The accel package has
  no symbol that's imported by `minecraft_bot`. The reverse direction
  is fine: accel may borrow Python-reference test fixtures during
  parity testing.
- **Live integration is the parity tie-breaker.** When unit tests
  pass but the live-server suite fails, the live observation is
  authoritative and Python is patched first.
