# Implementation Plan: Protocol Foundation

**Branch**: `001-protocol-foundation` | **Date**: 2026-05-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-protocol-foundation/spec.md`

## Summary

Build the Minecraft Java Edition protocol-763 (v1.20.1) wire foundation in
Python (canonical reference) and Rust (parity mirror): primitive type codecs,
length-prefixed/zlib-thresholded framer, per-state packet registries, every
clientbound and serverbound packet for handshaking / status / login / play
states, and a `Connection` lifecycle that drives a bot from TCP socket open to
Play state, keeps it alive via keep-alive answer, surfaces every disconnect as
a typed error, and serializes serverbound writes in strict FIFO order. Includes
a `WireLog` capture and an offline replay engine. Each packet lives in its own
file under `protocol/v763/packets/{state}/{direction}/`. Scope is single
`Connection` per process; the architecture is multi-bot-ready (no shared
mutable globals; `Send`/`Sync` types in Rust; per-connection isolation in
Python). Online-mode authentication is out of scope; the API reserves
`Connection.online_*` factories without implementing them.

## Technical Context

**Language/Version**: Python 3.11+ (canonical reference); Rust stable, edition 2021 (parity mirror)
**Primary Dependencies**:
- Python core — stdlib only: `asyncio`, `struct`, `zlib`, `dataclasses`, `enum`, `socket`, `pathlib`, `logging`, `time`, `json`, `uuid`, `typing`
- Rust core — `tokio` (features `net`, `io-util`, `sync`, `time`, `macros`, `rt-multi-thread`), `bytes`, `flate2`, `thiserror`, custom in-tree NBT (no external NBT crate, keeps dependency tree shallow per Constitution VI)
- Test-only: `pytest`, `pytest-asyncio`, `pytest-benchmark`; `cargo nextest` (optional)
- Optional extras (deferred): `numpy`, `gymnasium`, `pyo3-asyncio`, `pyo3` — only behind `pip install minecraft-bot[ml]` / `--features ml` extras, not part of this milestone

**Storage**: filesystem only. Wire-log captures live as JSON Lines (`.jsonl`) with hex-encoded raw payloads (see `contracts/wire-log-format.md`). Golden-byte test fixtures live in `protocol-data/v763/golden_bytes/`. No database.

**Testing**:
- Python: `pytest -q` (unit) + `pytest -m live -q` (integration against live Paper). `pytest-benchmark` for SC-009 latency budget verification.
- Rust: `cargo test` (unit codec round-trip) + `cargo test --features live-smoke` (integration). Per-packet `criterion` benches for parity check with Python budget.
- Cross-language: a single `tools/cross_check.py` script encodes test vectors with both implementations and asserts byte-equality.

**Target Platform**: Linux / macOS / Windows (incl. WSL2). Python 3.11+; Rust stable. Test server is Paper 1.20.1 at `172.26.160.1:25565`, online_mode=false.

**Project Type**: Library / framework. Monorepo with sibling `python/` and `rust/` packages plus shared `protocol-data/`.

**Performance Goals**:
- Decode-and-dispatch latency ≤ **5 ms median**, ≤ **25 ms p99** on commodity hardware (Ryzen 5 / Core i5 class) at steady-state play stream (SC-009).
- Live-server smoke test (US1+US2+US3) completes in < **2 min** wall-clock (SC-008).
- Bot stays connected ≥ **10 min** without keep-alive timeout (SC-003).

**Constraints**:
- Zero runtime deps in Python core (Constitution VI).
- Architecture must be multi-bot-compatible: no shared mutable globals; per-connection state; types `Send`/`Sync` (FR-017a).
- API: separate factory constructors for auth modes; no `online=` boolean (FR-017b). This milestone exposes only `Connection.offline(...)`.
- Strict FIFO for serverbound writes from a single `Connection` (FR-013a).
- Auto-reconnect opt-in via `auto_reconnect` flag, default off; per-connection state always discarded between sessions (FR-007a).
- Offline-mode only; encryption / online auth deferred but namespace reserved.
- Single live `Connection` per process scope; no `BotPool` in this milestone.

**Scale/Scope**:
- Protocol 763 only.
- ~11 status + login packets, ~111 clientbound play packets, ~33 serverbound play packets → ~155 packet files per language.
- 10 primitive codecs (VarInt, VarLong, String, UUID, Position, Identifier, BitSet, NBT, Slot, ChatComponent).
- 4 connection states (Handshaking, Status, Login, Play). Configuration state is **not present** in protocol 763.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Reviewing the seven principles from `.specify/memory/constitution.md` v1.0.0.

### Initial gate (pre-Phase 0)

| # | Principle | How this plan complies | Verdict |
|---|---|---|---|
| I | Python Is the Source of Truth | Python lands first; cross-language parity rule (constitution Workflow section) requires Python reference before Rust ships. Python `dataclass` packet types are the schema definition; Rust mirrors them. | ✅ |
| II | One Packet, One File; Versions in Folders | Project Structure mandates `python/.../protocol/v763/packets/{state}/{direction}/{snake_case_name}.py` and identical Rust layout. Block-state / registry tables also under `v763/data/` (deferred but named). | ✅ |
| III | PyTorch-Style Composable API | `Connection` is a stateful module with `on_packet` / `before_send` hooks; decoded packets are `dataclass(frozen=True, slots=True)` in Python and `#[derive(Clone, Debug)]` structs in Rust. The interface leaves a `Bot(nn.Module)`-style higher layer (next milestone) trivially constructible above. | ✅ |
| IV | Bots Are Packet Sets, Not Entities | All `Connection` state is derived from inbound packets; no client-side physics or simulation in this milestone (deferred to Bot API). All outbound actions reduce to packet encodes. | ✅ |
| V | Live-Server Integration Testing (NON-NEGOTIABLE) | FR-021 mandates live Paper smoke test before merge; FR-022 names live-server probe as final authority over docs. CI / dev workflow gates live-suite via `pytest -m live`. | ✅ |
| VI | Zero Runtime Dependencies in Core | Python core uses only stdlib. Rust core uses `tokio`, `bytes`, `flate2`, `thiserror` — constitution explicitly permits this minimal set. ML/RL adapters and PyO3 are out of scope here, deferred to extras in later milestones. | ✅ |
| VII | Observability and Determinism | WireLog records every packet at full byte fidelity under logger `minecraft_bot.protocol`. Offline replay (FR-019) reproduces decoded state without network calls. Latency / disconnect events are typed and surface to user code. | ✅ |

**Initial gate: ✅ passes for all seven.** No Complexity Tracking entries needed at this point.

### Post-Phase 1 re-check

After completing data-model, contracts, and quickstart, re-evaluate:

| # | Principle | Re-check note | Verdict |
|---|---|---|---|
| I | Python Is the Source of Truth | `contracts/python-api.md` is normative; `contracts/rust-api.md` mirrors it field-for-field. | ✅ |
| II | One Packet, One File | Project structure unchanged; `data-model.md` lists every entity in its named file. | ✅ |
| III | PyTorch-Style Composable API | `contracts/python-api.md` exposes `Connection.on(packet_type)` and `await connection.send(packet)` with no global state. Hook subscription is composable. | ✅ |
| IV | Bots Are Packet Sets | `data-model.md` describes state as derived from packet stream; no parallel simulation. | ✅ |
| V | Live-Server Integration Testing | `quickstart.md` includes live-smoke command as the canonical "is it working" check. | ✅ |
| VI | Zero Runtime Dependencies | No new dependencies introduced in any contract. | ✅ |
| VII | Observability and Determinism | `contracts/wire-log-format.md` is a concrete, replayable format. | ✅ |

**Post-design gate: ✅ passes for all seven.** Plan ready for `/speckit-tasks`.

## Project Structure

### Documentation (this feature)

```text
specs/001-protocol-foundation/
├── plan.md              # This file (/speckit-plan)
├── research.md          # Phase 0 output (/speckit-plan)
├── data-model.md        # Phase 1 output (/speckit-plan)
├── quickstart.md        # Phase 1 output (/speckit-plan)
├── contracts/
│   ├── python-api.md    # Phase 1 — canonical Python public API
│   ├── rust-api.md      # Phase 1 — parity mirror for Rust
│   └── wire-log-format.md  # Phase 1 — JSONL replay format
├── checklists/
│   └── requirements.md  # (created later by /speckit-checklist)
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
MinecraftBot/
├── python/
│   ├── pyproject.toml
│   └── minecraft_bot/
│       ├── __init__.py             # public re-exports: Connection, ProtocolError, ...
│       ├── connection.py           # Connection class + offline factory + lifecycle
│       ├── framer.py               # length-prefix + zlib threshold framer
│       ├── errors.py               # typed error hierarchy (ProtocolError, ...)
│       ├── wire_log.py             # WireLog capture + offline replay
│       ├── _internal/              # not part of public API
│       │   ├── __init__.py
│       │   ├── lock.py             # serverbound FIFO write lock
│       │   └── decode_loop.py      # async decode-and-dispatch pipeline
│       ├── codec/
│       │   ├── __init__.py
│       │   ├── varint.py
│       │   ├── varlong.py
│       │   ├── string.py
│       │   ├── uuid.py
│       │   ├── position.py
│       │   ├── identifier.py
│       │   ├── bitset.py
│       │   ├── nbt.py
│       │   ├── slot.py
│       │   └── chat_component.py
│       └── protocol/
│           ├── __init__.py
│           └── v763/
│               ├── __init__.py
│               ├── registry.py     # (state, dir, id) -> packet class
│               ├── states.py       # ConnectionState enum
│               └── packets/
│                   ├── handshaking/serverbound/handshake.py
│                   ├── status/{clientbound,serverbound}/*.py
│                   ├── login/{clientbound,serverbound}/*.py
│                   └── play/{clientbound,serverbound}/*.py
│
├── rust/
│   ├── Cargo.toml
│   └── src/
│       ├── lib.rs
│       ├── connection.rs
│       ├── framer.rs
│       ├── errors.rs
│       ├── wire_log.rs
│       ├── codec/
│       │   ├── mod.rs
│       │   ├── varint.rs
│       │   ├── varlong.rs
│       │   ├── string.rs
│       │   ├── uuid.rs
│       │   ├── position.rs
│       │   ├── identifier.rs
│       │   ├── bitset.rs
│       │   ├── nbt.rs
│       │   ├── slot.rs
│       │   └── chat_component.rs
│       └── protocol/
│           └── v763/
│               ├── mod.rs
│               ├── registry.rs
│               ├── states.rs
│               └── packets/
│                   ├── handshaking/serverbound/handshake.rs
│                   ├── status/{clientbound,serverbound}/*.rs
│                   ├── login/{clientbound,serverbound}/*.rs
│                   └── play/{clientbound,serverbound}/*.rs
│
├── protocol-data/                  # Generated, shared, read-only by both packages
│   └── v763/
│       ├── packet_registry.json    # PrismarineJS minecraft-data snapshot pinned
│       ├── golden_bytes/
│       │   ├── primitives.json     # codec test vectors
│       │   └── packets/            # per-packet golden bytes (live captures)
│       └── live_captures/          # *.jsonl wire-log captures kept under VCS
│
├── tests/
│   ├── python/
│   │   ├── conftest.py
│   │   ├── unit/
│   │   │   ├── test_codec_varint.py
│   │   │   ├── test_codec_nbt.py
│   │   │   ├── test_framer.py
│   │   │   └── ...
│   │   ├── integration/
│   │   │   ├── test_us1_connect.py
│   │   │   ├── test_us2_decode.py
│   │   │   └── test_us3_send.py
│   │   ├── replay/
│   │   │   └── test_us4_replay.py
│   │   └── perf/
│   │       └── test_decode_latency.py  # SC-009 budget check
│   └── rust/
│       ├── codec_roundtrip.rs
│       ├── framer.rs
│       └── live_smoke.rs
│
├── tools/                          # Not shipped; helper scripts only
│   ├── generate_packet_skeletons.py    # codegen from packet_registry.json
│   ├── capture_session.py              # records *.jsonl into live_captures/
│   └── cross_check.py                  # python vs. rust byte parity
│
└── specs/001-protocol-foundation/...
```

**Structure Decision**: Monorepo with sibling `python/` and `rust/` packages,
sharing read-only `protocol-data/`. Both packages expose top-level
`minecraft_bot` (Python module) / `minecraft_bot` (Rust crate) and mirror
identical layouts under `protocol/v763/`. Tests split per-language; live-server
tests gated behind explicit markers (`pytest -m live`,
`cargo test --features live-smoke`). The `tools/` directory holds offline
helper scripts — packet-skeleton codegen from `protocol-data/v763/packet_registry.json`,
session capture for golden fixtures, and Python↔Rust byte-parity cross-check —
none of which ship inside the published packages.

## Complexity Tracking

> No constitution violations. Section intentionally empty.
