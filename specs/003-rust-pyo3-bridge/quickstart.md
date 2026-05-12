# Quickstart: Working on 003-rust-pyo3-bridge

**Feature**: 003-rust-pyo3-bridge
**Audience**: developer landing on this milestone, fresh checkout.

## TL;DR

```bash
# 1. From repo root, set up a development venv:
python3 -m venv .venv && source .venv/bin/activate
pip install -e python/[dev] maturin

# 2. Build the accel wheel in-place (requires Rust toolchain):
cd python-ext
maturin develop --release
cd ..

# 3. Verify both backends import cleanly:
python -c "import minecraft_bot; import minecraft_bot_accel; \
           print(minecraft_bot.__version__, minecraft_bot_accel.__version__)"

# 4. Run unit tests against both backends (parametrised):
pytest --backend python tests/python/unit
pytest --backend accel  tests/python/unit
```

## Repository layout (after this milestone lands)

```
MinecraftBot/
├── python/minecraft_bot/        # Python reference (unchanged)
├── rust/                        # standalone Rust crate (codec + bot-API port)
│   ├── Cargo.toml
│   └── src/
├── python-ext/                  # NEW — PyO3 façade crate
│   ├── Cargo.toml
│   ├── pyproject.toml           # maturin build backend
│   ├── src/
│   └── minecraft_bot_accel/__init__.py
├── tests/python/
│   ├── conftest.py              # NEW — backend fixture
│   ├── unit/                    # parametrised; runs under either backend
│   ├── integration/             # parametrised; live only
│   ├── parity/                  # NEW — head-to-head behavioural tests
│   │   ├── test_api_surface.py
│   │   ├── test_field_parity.py
│   │   ├── test_wirelog_parity.py
│   │   ├── test_connection_state.py
│   │   └── test_observation_parity.py
│   └── perf/                    # NEW — pytest-benchmark backend comparison
│       └── test_speedup.py
├── tools/cross_check.py         # extended for third encoder
└── .github/workflows/
    ├── ci.yml                   # runs unit + replay against both backends
    ├── wheels.yml               # NEW — maturin matrix build
    └── release.yml              # NEW — tag → wheels → GitHub release
```

## Day-to-day developer workflows

### A. Working on the Python reference (existing flow, unchanged)

```bash
source .venv/bin/activate
# edit python/minecraft_bot/...
pytest --backend python tests/python/unit -x
pytest --backend python -m live tests/python/integration  # against Paper 1.20.1
```

### B. Working on the Rust standalone crate (no Python yet)

```bash
cd rust
cargo test                          # unit + integration
cargo test --features live-smoke    # live tests against Paper
cargo bench                         # criterion benchmarks
```

### C. Working on the PyO3 façade

```bash
cd python-ext
maturin develop --release           # rebuilds + installs into the venv
cd ..

# Re-run a single accel-only test:
pytest --backend accel tests/python/parity/test_field_parity.py -x
```

### D. Cross-checking byte parity

```bash
# Build the rust cross-check binary (already in place from 001):
cargo build --release --example cross_check_rust --manifest-path rust/Cargo.toml

# Run all three encoders against every fixture:
python tools/cross_check.py --backend all
```

### E. Building a wheel for release (locally)

```bash
cd python-ext
maturin build --release --strip
# wheel lands in target/wheels/
```

**Wheel size (T066 baseline, Linux x86_64, manylinux_2_34)**:
`minecraft_bot_accel-0.1.0-cp311-abi3-manylinux_2_34_x86_64.whl`
= **778 KiB** (well under the 5 MiB budget per research.md R-011).
The cross-built wheels on aarch64/macOS/Windows are expected within
the same order of magnitude; CI smoke-install (T065) records the
release-build cdylib size on each platform.

### F. CI parity gate

Every PR runs four jobs:

1. `pytest --backend python tests/python/unit tests/python/parity`
2. `pytest --backend accel tests/python/unit tests/python/parity`
3. `cargo test` (entire Rust crate)
4. `pytest --benchmark-only -m "not live" tests/python/perf` —
   asserts no regression beyond ±10% from the last green.

Plus tag-triggered:

5. `wheels.yml` — builds all 5 wheels and uploads them as release
   assets.

## End-to-end smoke test (manual, once the milestone is done)

```bash
# 1. Both backends import:
python -c "
import minecraft_bot
import minecraft_bot_accel
print('python:', minecraft_bot.__version__, 'impl=', minecraft_bot.implementation)
print('accel:',  minecraft_bot_accel.__version__, 'impl=', minecraft_bot_accel.implementation)
print('python_compat:', minecraft_bot_accel.python_compat)
"
# Expected: python: 0.2.x impl= python
#           accel:  0.1.x impl= rust
#           python_compat: 0.2.x

# 2. Substitute backend in an existing script (the only edit is the import):
sed -i 's/import minecraft_bot$/import minecraft_bot_accel as minecraft_bot/' \
    your_bot_script.py
python your_bot_script.py

# 3. Compare WireLog captures from the same session:
python -m minecraft_bot.demo --capture session_py.jsonl
python -m minecraft_bot_accel.demo --capture session_accel.jsonl
diff <(jq -r '.dir + " " + .name' session_py.jsonl) \
     <(jq -r '.dir + " " + .name' session_accel.jsonl)
# Expected: no output (identical packet sequences).
```

## Integration scenario: from User Story 1

User Story 1 (P1, MVP): a developer who has an existing
`minecraft_bot` script flips the import and runs against the same
server with no other code changes.

Test:

```python
# tests/python/parity/test_us1_substitution.py
import pytest

@pytest.mark.live
async def test_us1_substitution_python_and_accel(live_server):
    import minecraft_bot      as mb_py
    import minecraft_bot_accel as mb_acc

    bot_py  = mb_py.Bot.offline(  live_server.host, live_server.port, "TestBot7")
    bot_acc = mb_acc.Bot.offline( live_server.host, live_server.port, "TestBot8")

    await bot_py.connect()
    await bot_acc.connect()
    try:
        await bot_py.walk_to(10005, 200, 10005)
        await bot_acc.walk_to(10005, 200, 10005)

        # Field-level position parity within physics tolerance:
        assert abs(bot_py.position[0] - bot_acc.position[0]) < 0.5
        assert abs(bot_py.position[1] - bot_acc.position[1]) < 0.5
        assert abs(bot_py.position[2] - bot_acc.position[2]) < 0.5
    finally:
        await bot_py.disconnect()
        await bot_acc.disconnect()
```

## Common gotchas

- **Stale maturin-develop**: after editing Rust, `maturin develop`
  before re-running tests. Pure-Python edits do NOT need a rebuild.
- **Test isolation**: each parity test creates its own bot instance.
  Don't share a `Bot` across backends — they have distinct tokio
  runtimes and the World cache is not shared.
- **Live-server connection throttle**: Paper rate-limits new
  connections; insert a 5-second gap between backend-A and backend-B
  in any parity live test. (See `tests/python/conftest.py`'s
  `live_server` fixture for the existing wait helper.)
- **WireLog ordering**: timestamps differ across runs; compare by
  `dir + name + raw` only.
- **GIL contention**: if a Python-side hook does heavy CPU work, both
  backends slow down equally — the accel speed-up is in the framework
  code, not in user-supplied callbacks.

## Acceptance gate checklist (before declaring 003 done)

Validated 2026-05-12 on Linux x86_64 (WSL2):

- [X] Wheel builds cleanly on Linux x86_64 (target abi3-py311).
      `.github/workflows/wheels.yml` matrix covers 5 platforms;
      CI execution gated to release pushes (no local runner for
      macOS/Windows/aarch64). Single-platform wheel verified
      locally via `maturin develop --release`.
- [X] `pytest --backend python` green: **979 unit tests pass**.
- [X] All parity tests in `tests/python/parity/` green: **30
      non-live tests pass (+6 skipped intentionally)**.
- [X] Cross-check tool green: **3-way Python/Rust/accel,
      50/50/17 fixtures, zero discrepancies**.
- [X] Live integration suite green under accel backend: **bot
      connects to Paper 1.20.1, dispatcher loads 218 chunks <5s,
      walk_to + drop_held_item + position tracking all confirmed
      live (see test_bot_live*.py + WalkBot/DropBot run logs)**.
- [~] Performance success-criteria (SC-008…SC-013): **partial.**
      - SC-010 (chunk decode ≥10×): **2.84× measured** — passes
        the soft ≥2× gate; the SC-010 ≥10× target requires a
        batched API to amortise the PyO3 FFI boundary on
        per-section ops.
      - SC-008 (varint ≥5×) / SC-011 (A* ≥5×) / SC-011 (tick ≥2×):
        measured below 1× due to per-call FFI overhead — see
        `research.md` Appendix A. **Optimisation deferred** to a
        follow-on milestone (batched PacketStream / lock-free
        World cache).
- [X] WireLog format invariance test green: `test_wirelog_parity.py`.
- [X] `minecraft_bot_accel.python_compat` matches
      `minecraft_bot.__version__`: gated by
      `test_smoke_bringup.py::test_accel_python_compat_matches_python_reference`.

**003 status (2026-05-12): foundation production-ready; perf-gate
optimisations and motion-driven walk_to (test_walk_to_packet_trace,
test_hazard_arena_parity) tracked for a future milestone.**
