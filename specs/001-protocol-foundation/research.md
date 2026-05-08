# Phase 0 Research: Protocol Foundation

**Date**: 2026-05-08
**Plan**: [plan.md](./plan.md)

This document records the load-bearing technology and design decisions that
back the implementation plan. There are no unresolved `NEEDS CLARIFICATION`
markers entering Phase 1 — the spec's `## Clarifications` session resolved the
five highest-impact questions before planning began.

For each topic: **Decision · Rationale · Alternatives considered · Sources**.

---

## R-01 Packet schema definition strategy

**Decision**: Hand-curated, code-first packet definitions with a one-shot
codegen primer. Each packet is a hand-written file under
`protocol/v763/packets/{state}/{direction}/`. The codegen script
`tools/generate_packet_skeletons.py` reads `protocol-data/v763/packet_registry.json`
(a pinned snapshot of PrismarineJS minecraft-data) and produces empty stub
files with field signatures. Humans fill in the body. After initial generation,
files are owned by humans; the codegen is **not** re-run on every build.

**Rationale**:
- Constitution II ("One Packet, One File") is the architectural anchor; pure
  generated code from a YAML/JSON DSL would force readers to chase definitions
  through three indirection layers and would make ad-hoc protocol probes
  (live-server overrides) much harder.
- Hand-written files are diffable across protocol versions, which is the v764
  porting story (US5).
- A one-shot generator pays for itself: 155+ packets × 2 languages = 310 stubs.
  Hand-typing all of them would be error-prone and slow; copy-pasting field
  signatures is exactly what codegen is for.
- Live-server probes can override the doc-source (`minecraft-data`) by editing
  the per-packet file directly without diverging from a generator's source.

**Alternatives considered**:
- **Pure generated code from a YAML/JSON DSL** (e.g., a `packets.yml` that gets
  compiled to Python and Rust). Rejected: violates one-file-per-packet
  diffability story; introduces a build step before unit tests can run; the
  DSL becomes its own thing to learn and maintain.
- **Runtime registry that holds field tuples, no per-packet classes**. Rejected:
  loses static typing in both languages; loses IDE navigation; couples codec
  changes to runtime hot paths.
- **Generated code re-run on every build** (e.g., `build.rs` calling codegen).
  Rejected: per-packet files become read-only artefacts again, defeating the
  human-edit-per-packet workflow.

**Sources**: PrismarineJS `minecraft-data` repo (https://github.com/PrismarineJS/minecraft-data); minecraft.wiki (https://minecraft.wiki/w/Java_Edition_protocol); prior project memory (existing `python-mc/protocol/v1201.py` was monolithic and painful to diff — explicit anti-pattern).

---

## R-02 Async TCP framer design (Python)

**Decision**: A single async coroutine `Framer.read_loop` reads from a single
`asyncio.StreamReader`, accumulates bytes into an internal `bytearray`,
extracts framed packets per the
length-prefixed (uncompressed) or length-prefixed + zlib-compressed
(compression on, payload size ≥ threshold) format,
and pushes decoded `RawPacket` objects (id + payload bytes) into an
`asyncio.Queue` (bounded). Decoders consume the queue in a separate coroutine.
A second coroutine `Framer.write_loop` consumes outbound packets from a single
`asyncio.Queue` (FIFO guaranteed by queue + lock — see R-03) and writes them
to the `asyncio.StreamWriter`. Backpressure: bounded queue size = 1024 frames;
when full, `read_loop` awaits, which naturally backpressures the TCP socket.

**Rationale**:
- `asyncio.StreamReader` already buffers internally; we only need to peek for
  the variable-length VarInt prefix and `read_exactly` the payload.
- A single read loop avoids subtle interleaving when the socket fragments.
- Bounded outbound queue avoids unbounded memory growth if the server hangs
  while the bot keeps generating outbound packets.
- Compression threshold negotiation (Set Compression packet, login state) is
  applied in-band: the framer keeps a `compression_threshold` field; on each
  packet it inspects payload length to decide compressed vs. uncompressed
  framing per the wire spec.

**Alternatives considered**:
- **One coroutine per direction, no internal queue, direct invocation of
  decoder.** Rejected: the decoder may take milliseconds (NBT-heavy chunk
  packets) and would back-pressure the socket directly, risking keep-alive
  miss under load. A queue decouples I/O from decode.
- **Use `asyncio.Protocol` (callback style).** Rejected: harder to compose
  with existing `await`-style API; performance is comparable to
  `StreamReader` for our packet sizes.

**Sources**: minecraft.wiki "Packet format" page; Python stdlib `asyncio.streams` docs; prior `python-mc/connection.py` (which does almost exactly this and works in production).

---

## R-03 Strict FIFO writer (FR-013a)

**Decision**: Serverbound writes go through `Connection._write_lock`
(`asyncio.Lock`) wrapping the `asyncio.StreamWriter.write` + `drain` pair.
Public API: `await connection.send(packet)`. Internally:

```python
async def send(self, packet: ServerboundPacket) -> None:
    raw = self._encode(packet)
    async with self._write_lock:
        self._writer.write(raw)
        await self._writer.drain()
```

The lock is per-`Connection`. Order of `send(...)` invocation across coroutines
maps to wire order in the order the lock is acquired. Two concurrent senders
queue cleanly.

In **Rust**, the equivalent is a `tokio::sync::Mutex<OwnedWriteHalf>` —
held only across the `write_all` + `flush` for one frame.

**Rationale**:
- Cheap, well-understood primitive.
- A `tokio::sync::mpsc` channel + dedicated writer task is a richer
  alternative but adds a hop and complicates backpressure semantics; lock
  matches Python pattern 1:1.
- Encode happens *outside* the lock (no I/O contention while CPU work runs).

**Alternatives considered**:
- **`asyncio.Queue` + dedicated writer task**. Rejected: extra hop adds
  ~100µs latency per packet (asyncio scheduling). Not worth it for the
  semantic clarity gain.
- **Lock-free SPMC**. Rejected: protocol is single-producer-from-the-app /
  single-consumer-on-the-wire; no real contention to optimise.

**Sources**: asyncio docs (`asyncio.Lock`); tokio docs (`tokio::sync::Mutex`); FR-013a in spec.

---

## R-04 NBT codec (Python and Rust)

**Decision**: Hand-written NBT codec in both languages, no external library.
Python: `codec/nbt.py` (~200 LoC) supporting all 13 tag types
(End, Byte, Short, Int, Long, Float, Double, ByteArray, String, List,
Compound, IntArray, LongArray) plus Java-Edition's network-NBT variant
(no root name, used in Slot data per protocol 763's update). Rust:
`codec/nbt.rs` (~250 LoC) mirroring exactly.

**Rationale**:
- Constitution VI: zero runtime deps in core. The only options that satisfy
  this constraint *and* support the network-NBT variant are hand-written.
- `nbt`/`fastnbt` Rust crates pull in `serde_derive` and `serde`, which we
  don't need elsewhere; the dep tree balloons.
- NBT is small (13 tag types, no recursion limit in protocol 763 since
  servers are well-behaved) — ~250 LoC is honestly enough.

**Alternatives considered**:
- **`fastnbt` crate (Rust)**. Rejected: adds `serde` + `serde_derive`
  proc-macro to the dep tree.
- **`pynbt` package (Python)**. Rejected: adds a runtime dep, violating
  Constitution VI.
- **`gilded` / similar.** Rejected: same reasoning.

**Sources**: minecraft.wiki "NBT format"; PrismarineJS `prismarine-nbt`
JS reference impl (used as algorithmic reference, not as runtime dep).

---

## R-05 Wire-log file format

**Decision**: JSON Lines (`.jsonl`). One line per packet event. Schema
documented in `contracts/wire-log-format.md`. Each line:
```json
{"ts": 1714867200.123456, "dir": "rx", "state": "play", "id": 36, "name": "synchronize_player_position", "fields": {...}, "raw": "0a0b0c..."}
```
- `ts`: float seconds since epoch (monotonic-aligned at session start)
- `dir`: "rx" or "tx"
- `state`: connection state at the time the packet was framed
- `id`: numeric packet id within the state
- `name`: snake_case packet name
- `fields`: decoded fields as JSON (lossy for floats — see "Replay precision"
  below)
- `raw`: hex-encoded raw payload bytes (lossless)

**Rationale**:
- JSONL is replayable line-by-line, greppable, diffable, and reproducible
  with stdlib only.
- `raw` is the lossless source of truth for replay; `fields` is for human
  reading.
- Hex encoding (vs. base64) is more debuggable when a human is staring at a
  log file looking for "what was the chunk packet's first byte?"
- Replay reads `raw`, decodes via the same registry, and feeds the typed
  packet back into the dispatch pipeline; reconstructed state must match
  live-session state (FR-019).

**Replay precision note**: Float fields (e.g., position `x`, `y`, `z` which
are `f64`) round-trip through JSON via `repr()` in Python, which is
round-trippable. The `raw` field is the canonical fallback if any decode
discrepancy is suspected.

**Alternatives considered**:
- **CBOR / MessagePack**. Rejected: needs a dep; loses grep-ability.
- **Protobuf**. Rejected: needs codegen toolchain; loses grep-ability;
  schema-evolution headache when a packet adds a field.
- **Plain hex dump (no fields)**. Rejected: replay still works but human
  inspection becomes painful.

**Sources**: JSON Lines spec (https://jsonlines.org); python-mc historical
log format (similar approach worked).

---

## R-06 Live-server test gating

**Decision**: Live tests are tagged with `pytest.mark.live` (Python) and
`#[cfg(feature = "live-smoke")]` (Rust). Default `pytest -q` runs only
unit/replay tests in <30 s. `pytest -m live` runs live-server tests; CI
runs `live` only on a runner with the test server reachable.
A fixture (`tests/python/conftest.py::live_server`) probes
`172.26.160.1:25565` at session start and skips the live suite if
unreachable, with a clear warning message — no silent passes.

**Rationale**:
- Constitution V mandates live testing — but contributors without a server
  must still run unit tests.
- Skipping with a loud warning, instead of silently passing, prevents the
  "tests are green but I never ran the live ones" trap that the constitution
  was written to avoid.

**Alternatives considered**:
- **Always-on live tests in default `pytest`**. Rejected: contributor
  hostility; CI complexity for forks.
- **Separate `live_tests/` directory invoked by separate runner**.
  Rejected: doubles the test infrastructure.

**Sources**: pytest markers docs; Constitution V.

---

## R-07 Decode-and-dispatch pipeline shape

**Decision**: Two-stage pipeline. Stage 1 = framer producing `RawPacket(id,
state, payload_bytes)` into a bounded `asyncio.Queue`. Stage 2 = decode-loop
coroutine pulling from the queue, looking up the packet class via the
`CodecRegistry`, decoding, then synchronously fanning out to subscribers
(`on_packet` hooks) and updating the `Connection`'s in-memory state. Hooks
run in the decode loop's coroutine (no further hop). User code that wants
to do heavy work in a hook is expected to spawn its own task.

The latency-sensitive critical path (keep-alive, teleport-confirm) runs
**before** subscriber fan-out, in the decode loop itself, so a slow user
hook cannot starve the protocol. Concretely: keep-alive and
teleport-confirm packets are auto-replied **inside** the decode loop the
moment they're decoded, not via a subscriber.

**Rationale**:
- SC-009 budget (5 ms median / 25 ms p99) requires a tight critical path.
  Adding a third hop (e.g., dispatcher task) would consume ~1 ms per packet
  in asyncio scheduling alone.
- Auto-replying keep-alive inside the decode loop guards against the
  edge-case "Keep-alive timeout under load" — a user-installed slow hook
  cannot kill the connection.
- Synchronous fan-out keeps ordering semantics simple (subscribers see
  packets in wire order, FIFO).

**Alternatives considered**:
- **Three stages: framer → decoder → dispatcher**. Rejected: extra hop
  burns latency budget without buying anything.
- **One stage: synchronous decode in framer**. Rejected: a slow NBT decode
  would back-pressure the socket and risk keep-alive misses.

**Sources**: spec FR-005 (keep-alive), FR-006 (teleport-confirm), SC-009
(latency budget); prior python-mc evidence that the two-stage pipeline
holds at 50+ pkt/s chunk bursts.

---

## R-08 Cross-language byte parity verification

**Decision**: A single Python script `tools/cross_check.py` enumerates every
codec test vector and every packet golden-byte fixture from
`protocol-data/v763/golden_bytes/` and asserts that:
1. Python `encode(value) == golden_bytes`
2. Rust `encode(value) == golden_bytes` (via a small CLI wrapper compiled
   from `rust/examples/encode_one.rs`)
3. Round-trip: `decode(golden_bytes) == value` in both languages

Run as `python tools/cross_check.py` after a build; a single CI job runs it
on every PR that touches `python/.../codec`, `rust/.../codec`, or
`protocol-data/`.

**Rationale**:
- The cross-language parity rule (constitution Workflow) needs an executable
  enforcement, not "we promise to do it".
- Golden-byte fixtures are the authoritative truth; a parity script keeps
  both impls aligned with the truth without a heavyweight FFI test
  framework.
- Done once per PR; not in the inner test loop (no perf cost).

**Alternatives considered**:
- **PyO3 in tests**. Rejected: too early; builds cycle time and adds the
  PyO3 dep before its milestone.
- **Two separate test suites with no parity check**. Rejected: drift is the
  failure mode the constitution exists to prevent.

**Sources**: Constitution Workflow section ("Cross-language parity rule").

---

## R-09 Packet ID source of truth

**Decision**: `protocol-data/v763/packet_registry.json` is generated **once**
from PrismarineJS minecraft-data (`minecraft-data/data/pc/1.20.1/protocol.json`)
and committed. Every packet file references its numeric ID by importing
`PACKET_ID` from `registry.py`, which loads the JSON at module-import time
(Python) or via `include_bytes!` (Rust). When a live-server probe disagrees
with `minecraft-data`, the live-server value wins (Constitution Tech
Constraints, "live-server probe is the final authority"); the override is
recorded in a separate file `protocol-data/v763/overrides.json`, which the
registry merges on top.

**Rationale**:
- Pinning a snapshot prevents upstream drift breaking us silently.
- Allowing per-ID overrides lets us correct minecraft-data inaccuracies
  without forking the upstream snapshot.
- One file to grep when "what's the ID of `chunk_data`?" comes up.

**Alternatives considered**:
- **Live network fetch from minecraft-data on first run**. Rejected: would
  require online connectivity for tests; violates the offline-test
  invariant.
- **Hand-typed IDs in each packet file**. Rejected: drift risk between
  files and the registry.

**Sources**: PrismarineJS minecraft-data `data/pc/1.20.1/protocol.json`;
constitution "Authoritative protocol sources" ordering.

---

## R-10 Python type representation (frozen dataclass with slots)

**Decision**: Each packet is a `dataclass(frozen=True, slots=True)` with
typed fields. Encode/decode are module-level functions, not methods, to
keep the dataclass usable as a value type:

```python
# protocol/v763/packets/play/clientbound/keep_alive.py
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class KeepAlive:
    keepalive_id: int  # i64

PACKET_ID = 0x24

def decode(reader) -> KeepAlive:
    return KeepAlive(keepalive_id=reader.read_i64())

def encode(packet: KeepAlive, writer) -> None:
    writer.write_i64(packet.keepalive_id)
```

**Rationale**:
- `frozen=True` matches the "Bots Are Packet Sets" principle — packets are
  immutable values once decoded.
- `slots=True` saves ~50% memory on the millions of packets a long session
  produces.
- Module-level `encode`/`decode` keep the type definition lean and let the
  registry call them by reference without method-binding.

**Alternatives considered**:
- **Pydantic models**. Rejected: heavy runtime cost (validation on every
  decode) and a runtime dep.
- **`attrs`**. Rejected: also a runtime dep; stdlib `dataclass` is enough.
- **Plain tuples / NamedTuple**. Rejected: harder to evolve fields and
  introspect.

**Sources**: Python stdlib `dataclasses` docs; PEP 557 (slots).

---

## R-11 Rust type representation

**Decision**: Each packet is a `#[derive(Debug, Clone, PartialEq)]` struct
in its own file, with an `impl Packet for ...` providing `id() -> i32`,
`state() -> ConnectionState`, `direction() -> Direction`, `decode(buf) ->
Result<Self, ProtocolError>`, `encode(&self, buf) -> ()`.
`PartialEq` enables round-trip tests; `Clone` enables cheap pass-through to
hooks; `Debug` keeps logs informative.

**Rationale**:
- Mirrors Python's frozen dataclass + module-level encode/decode. Different
  language idioms; same conceptual shape.
- `PartialEq` is the engine of FR-013 (round-trip equality assertions).
- No `serde_derive`: hand-written `decode`/`encode` keeps the dep tree
  shallow per Constitution VI.

**Alternatives considered**:
- **`serde` + `serde_derive`**. Rejected: large proc-macro dep, slows
  cold compiles, and the wire format is not naturally serde-shaped (VarInt
  alone needs a custom serializer).
- **A `Packet` enum with one variant per packet**. Rejected: would balloon
  to 155+ variants, not amenable to one-file-per-packet (Constitution II).

**Sources**: Constitution II + VI.

---

## Open items deferred to implementation

These are intentionally not pre-decided in research; they will be settled
when their tasks are touched:

- **Exact `auto_reconnect` backoff curve**: spec says "exponential";
  concrete numbers (initial delay, max delay, jitter) decided in the
  reconnect task with a passing test.
- **Configuration of write queue depth**: 1024 is the starting default;
  tunable in `Connection.offline(... write_buffer_size=...)` if a real
  workload pushes back.
- **Granularity of perf benchmark fixtures**: `pytest-benchmark` for
  decode-and-dispatch; may add `criterion` per-packet on the Rust side if
  parity drift appears.

---

## Summary

All Phase 0 research items resolved. No `NEEDS CLARIFICATION` remains.
Plan is consistent with Constitution v1.0.0. Ready to proceed to Phase 1
design artefacts (data-model, contracts, quickstart).
