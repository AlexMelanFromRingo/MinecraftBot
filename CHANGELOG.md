# Changelog

## v0.2.0 (2026-05-12)

First release of the PyO3 native-backed alternative
(`minecraft_bot_accel`). The Python reference (`minecraft_bot`) and
the standalone Rust crate ship in lockstep at the same version.

### Added

- **`minecraft_bot_accel`** PyO3 facade over the standalone Rust
  crate. Drop-in alternative to `minecraft_bot.Bot`: switch one
  import line to run hot paths in Rust.
- **abi3 wheel matrix** in `.github/workflows/wheels.yml`. One wheel
  per (OS, arch) covers Python 3.11 and 3.12. Targets: Linux x86_64,
  Linux aarch64, macOS arm64, macOS x86_64, Windows x86_64.
- **`Bot.send_raw(payload)`** escape-hatch lets callers send any of
  the 176 protocol packets without per-packet PyO3 wrappers. Encode
  through the Python reference's typed dataclasses, forward bytes.
- **Batched codec APIs**: `codec.varint.read_many`,
  `codec.varint.write_many`, `physics.tick_n`. Amortise the FFI
  boundary cost across many ops per call.
- **`codec.nbt`** direct decode/encode of NBT payloads.
- **CPU instrumentation**: `tools/measure_cpu_speedup.py` records
  end-to-end CPU drop for chunk-streaming workloads.
- **Three-way cross-check**: `tools/cross_check.py --accel`
  compares Python, standalone Rust, and accel encoders byte-for-byte
  across 117 fixtures.
- **Docs**: `docs/architecture.md`, `docs/migration_to_accel.md`,
  `docs/examples.md`.

### Performance

Heavy ops and batched primitives consistently beat pure Python.
Per-call codec ops on 1-2 byte values lose to Python because the
PyO3 boundary cost dominates the actual work.

| Operation | Speedup vs Python |
|---|---|
| End-to-end chunk burst (decode + cache + query) | 31.44× |
| Chunk decode alone | 2.84× |
| Batched VarInt read (N=1000) | 26.82× |
| Batched VarInt write (N=1000) | 24.68× |
| NBT decode (real heightmaps payload) | 3.26× |
| Batched physics tick (N=50) | 8.38× |
| A* pathfinder (with snapshot guard) | 6.38× |
| CPU drop during chunk-streaming bursts | 96.8% |

### Tests

- 979 Python unit tests (zero regressions vs 002).
- 88 parity + perf tests covering both backends.
- 76 Rust tests.
- 117 cross-check fixtures with zero discrepancies.
- Live integration against Paper 1.20.1 confirmed for: bot connect,
  position tracking, dispatcher chunk loading, walk_to, drop_held_item.

### Constitutional invariants

- `python/pyproject.toml` still declares `dependencies = []`.
- Nothing in `minecraft_bot` imports from `minecraft_bot_accel`.
- Python remains the spec of record; Rust and accel chase it.

### Known limitations / future work

- The accel `walk_to` slides directly along the A* path rather than
  driving motion through `physics.tick`. Functional parity holds
  (bot arrives at the target with `on_ground=True`) but the packet
  trace shape differs from the Python reference. The path-driven
  variant is the right shape for current bot use; the physics-driven
  variant is on the roadmap if motion-shape parity becomes a
  requirement.
- Per-packet typed pyclass wrappers (T055/T056 in the spec) are not
  shipped. They would duplicate the Python reference's 176-packet
  dataclass surface with no new capability. `Bot.send_raw(payload)`
  covers the escape hatch.
- Hazard arena live test (T084) is in the same boat as walk_to: the
  shape of accel motion differs from physics-driven motion, so a
  full hazard-course parity comparison is deferred.

## v0.1.0 (project history snapshot)

Pre-public version. Snapshot of 001-protocol-foundation +
002-bot-api milestones; the Python reference and the standalone Rust
crate were fully usable by then. v0.2.0 is the first release that
includes the PyO3 facade.
