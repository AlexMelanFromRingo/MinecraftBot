# Phase 1 Data Model: Protocol Foundation

**Date**: 2026-05-08
**Plan**: [plan.md](./plan.md) · **Spec**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)

This document captures the entities, fields, relationships, validation
rules, and state transitions that fall out of the spec. It is normative
for the Python implementation; the Rust implementation mirrors it
field-for-field and verb-for-verb (see `contracts/rust-api.md`).

Each entity is listed with: **Purpose · Fields · Relationships · Validation ·
Lifecycle · File location**.

---

## E-1 `ConnectionState`

**Purpose**: enumerates the discrete protocol phases of a `Connection`.
Controls which packet IDs are valid in each direction at each moment.

**Fields** (enum variants):
- `HANDSHAKING`
- `STATUS`
- `LOGIN`
- `PLAY`

**Relationships**: every `Packet` carries a `state` discriminator that
must match the `Connection`'s current state at the moment of decode/encode.

**Validation**: integer-stable variant values for log/replay parity (e.g.,
`HANDSHAKING=0`, `STATUS=1`, `LOGIN=2`, `PLAY=3`). No `CONFIGURATION` —
that state was introduced in protocol 764 and is **not** in scope here
(spec Assumptions, last bullet).

**Lifecycle / state transitions**:
```text
HANDSHAKING --(next_state=STATUS in handshake)--> STATUS --(server closes)--> [end]
HANDSHAKING --(next_state=LOGIN in handshake)--> LOGIN --(login_success)--> PLAY --(disconnect)--> [end]
```
Transitions are **server-driven** for STATUS→[end], LOGIN→PLAY (via
LoginSuccess clientbound), and PLAY→[end] (via Disconnect clientbound or
TCP drop). Client-driven transitions: HANDSHAKING→{STATUS,LOGIN} via the
`Handshake` serverbound packet's `next_state` field.

**File location**: `python/minecraft_bot/protocol/v763/states.py`,
`rust/.../protocol/v763/states.rs`.

---

## E-2 `Direction`

**Purpose**: enumerates packet flow direction.

**Fields** (enum variants):
- `CLIENTBOUND` — server → client
- `SERVERBOUND` — client → server

**File location**: `python/minecraft_bot/protocol/v763/states.py` (co-located
with `ConnectionState`), `rust/.../protocol/v763/states.rs`.

---

## E-3 `ProtocolVersion`

**Purpose**: numeric identifier for the wire protocol in use. Selects the
packet schemas, registries, and data tables that apply to a `Connection`.

**Fields**:
- `number: int` — e.g., `763`
- `display_name: str` — e.g., `"1.20.1"` (informational only)

**Relationships**: every `Connection` is constructed with exactly one
`ProtocolVersion`; only `protocol 763` is implemented in this milestone.

**Validation**: `number > 0`. The runtime registry refuses to construct a
`Connection` for a `ProtocolVersion` whose `v{number}/` directory does
not exist.

**Lifecycle**: immutable for the lifetime of a `Connection`.

**File location**: `python/minecraft_bot/protocol/__init__.py`,
`rust/.../protocol/mod.rs`. Constants like `V_1_20_1 = ProtocolVersion(763, "1.20.1")`
live there.

---

## E-4 `Packet` (abstract concept)

**Purpose**: a typed message sent in either direction. The framework does
not have a single `Packet` base class — each packet is a distinct frozen
dataclass (Python) / struct (Rust) under
`protocol/v763/packets/{state}/{direction}/{snake_case_name}.py`.

**Module-level binding**: each packet file exports:
- the dataclass / struct (the packet's named fields)
- `PACKET_ID: int` — the numeric ID for this packet in its `(state, direction)`
- `decode(reader: Reader) -> Packet` — pure function consuming bytes
- `encode(packet: Packet, writer: Writer) -> None` — pure function producing bytes

The packet's `state` and `direction` are implied by its file path; the
registry (E-7) is built by walking the directory tree and pairs paths with
classes.

**Field types**: each packet's fields use only the primitive codecs (E-5).
No packet may invent its own ad-hoc serialization; everything reduces to
codec calls.

**Validation**: a packet's encoded form must round-trip to an equal value
(spec FR-013). Equality is defined by Python `==` on dataclass fields and
Rust `PartialEq` derive.

**Lifecycle**: packets are immutable values from creation to garbage-
collection. Decoded packets flow through `Connection.dispatch` to
subscribers and update internal state; sent packets flow through
`Connection.send` to the wire under the FIFO lock (FR-013a).

**File location**: `protocol/v763/packets/{state}/{direction}/{snake_case_name}.py` —
one file per packet (constitution II).

---

## E-5 Primitive codecs

**Purpose**: encode/decode pairs for the ten Minecraft wire types
required by protocol 763 (spec FR-010).

| Codec | Wire format | Python type | Rust type | File |
|---|---|---|---|---|
| VarInt | 1–5 bytes, 7 bits/byte, MSB continuation | `int` | `i32` | `codec/varint.{py,rs}` |
| VarLong | 1–10 bytes, 7 bits/byte, MSB continuation | `int` | `i64` | `codec/varlong.{py,rs}` |
| String | VarInt-prefixed UTF-8, max length per protocol | `str` | `String` | `codec/string.{py,rs}` |
| UUID | 16 bytes, two `i64` halves big-endian | `uuid.UUID` | `uuid::Uuid` | `codec/uuid.{py,rs}` |
| Position | packed 64-bit `xyz` (26-12-26 bits, signed) | `tuple[int,int,int]` | `(i32,i32,i32)` | `codec/position.{py,rs}` |
| Identifier | namespaced string (`namespace:path`) | `str` (`namespace:path`) | `Identifier { ns, path }` | `codec/identifier.{py,rs}` |
| BitSet | length-prefixed `i64` array | `set[int]` | `BitVec` (custom) | `codec/bitset.{py,rs}` |
| NBT | network NBT (no root name, all 13 tags) | nested `dict`/`list`/scalars | `NbtTag` enum | `codec/nbt.{py,rs}` |
| Slot | `bool` present + VarInt id + i8 count + NBT | `SlotData \| None` | `Option<SlotData>` | `codec/slot.{py,rs}` |
| ChatComponent | length-prefixed JSON string | `str` (raw JSON) | `String` | `codec/chat_component.{py,rs}` |

**Validation per codec**:
- VarInt: rejects > 5 bytes (overflow); raises `ProtocolError` (spec edge case).
- VarLong: rejects > 10 bytes.
- String: rejects > 32767 chars (server-side max for chat) — actual cap is
  per-field, but 32767 is the absolute upper bound.
- Position: signs preserved across the (26,12,26) packing.
- NBT: enforces type-tag/value consistency; empty compound vs. absent NBT
  is distinguished (spec edge case).

**Round-trip invariant**: for every `value: T`, `decode(encode(value)) == value`.
Tested via `protocol-data/v763/golden_bytes/primitives.json` fixtures
(spec FR-020).

---

## E-6 `Connection`

**Purpose**: the main entity. Owns the live wire link to a Minecraft
server. Drives the lifecycle from socket open to disconnect; maintains
the current `ConnectionState`; enforces FIFO write ordering; surfaces
disconnects as typed errors; optionally records a `WireLog`.

**Fields** (Python; Rust mirror identical):
- `version: ProtocolVersion`
- `host: str`, `port: int`
- `username: str` — for offline mode, the player display name
- `state: ConnectionState` — current phase
- `compression_threshold: int` — `-1` if disabled, else byte size
- `auto_reconnect: bool` — opt-in (FR-007a), default `False`
- `reconnect_policy: ReconnectPolicy | None` — backoff/limit settings, only
  consulted if `auto_reconnect=True`
- `write_buffer_size: int` — bounded outbound queue depth, default 1024
- `_reader: asyncio.StreamReader` — internal
- `_writer: asyncio.StreamWriter` — internal
- `_write_lock: asyncio.Lock` — FIFO guarantee (R-03)
- `_decode_loop: asyncio.Task` — internal
- `_dispatch_table: dict[type[Packet], list[Callable]]` — subscribers
- `_state_view: ConnectionStateView` — read-only snapshot of derived state
  (position, inventory, entities — though Bot API spec extends this)
- `wire_log: WireLog | None` — optional capture sink

**Construction** (FR-017b):
- `Connection.offline(host, port, username, *, version=V_1_20_1, auto_reconnect=False, reconnect_policy=None, write_buffer_size=1024, wire_log=None) -> Connection`

  This is the **only** factory in this milestone. Future milestones add
  `Connection.online_microsoft(...)` / `Connection.online_mojang(...)` as
  separate factories.

**Lifecycle**:
```text
construct (offline factory)
  -> connect()             # opens TCP, runs handshake → login → play
  -> [running]             # decode loop active, send() works
  -> disconnect()          # clean quit packet, closes socket
  -> [closed]              # send() raises ConnectionClosed
```
On unexpected drop:
- `auto_reconnect=False`: raises typed error to any awaiter; `[closed]`.
- `auto_reconnect=True`: restarts handshake on a new socket per
  `reconnect_policy`; per-connection state (position, inventory, observed
  entities) is **discarded** between sessions (FR-007a). Consumers
  observe a `Reconnected` event and must rebuild any locally tracked
  state.

**Validation**:
- `host`/`port`/`username` required.
- `version.number == 763` until other versions are implemented.
- `auto_reconnect=True` requires `reconnect_policy` to be non-None or
  defaults to `ReconnectPolicy()` (sensible defaults).

**File location**: `python/minecraft_bot/connection.py`,
`rust/.../connection.rs`.

---

## E-7 `CodecRegistry`

**Purpose**: maps `(state, direction, packet_id)` to the packet decoder
function and the packet class to its encoder. Built once per
`ProtocolVersion` at import time.

**Fields**:
- `by_id: dict[tuple[ConnectionState, Direction, int], type[Packet]]`
- `by_class: dict[type[Packet], tuple[ConnectionState, Direction, int]]`

**Construction**: at module import time, walk
`protocol/v763/packets/{state}/{direction}/*.py` (or use a generated
`__init__.py` index for performance), import each module, read `PACKET_ID`
and the dataclass, populate both maps. Override map merge per R-09.

**Validation**: every `(state, direction, packet_id)` triple must be unique;
violation is a startup error.

**Performance**: lookups are `O(1)` dict access; full registry materialized
once per process (since this milestone is single-`Connection`, even N
connections in future would share read-only registry). Per FR-017a, the
registry MUST be `Send`/`Sync` in Rust (immutable after construction →
free).

**File location**: `python/minecraft_bot/protocol/v763/registry.py`,
`rust/.../protocol/v763/registry.rs`.

---

## E-8 `WireLog`

**Purpose**: a chronological record of every packet flowing through a
`Connection`. May be written to JSONL on disk (R-05), streamed to a
`logging.Logger`, or replayed offline.

**Fields**:
- `entries: list[WireLogEntry]` — in-memory store (capped if streaming)
- `sink: WireLogSink` — write strategy (`InMemory`, `JsonlFile(path)`,
  `LoggerSink(logger)`, `Tee(...)`)
- `started_at: float` — `time.time()` at session start

**`WireLogEntry`** (matches the JSONL line schema, R-05):
- `ts: float` — seconds since `started_at` start
- `dir: Direction`
- `state: ConnectionState`
- `id: int`
- `name: str`
- `fields: dict | None` — JSON-encodable representation, may be omitted
- `raw: bytes` — lossless payload

**Replay**: `WireLog.replay(path) -> ReplayedConnection` — feeds entries
through the same registry / decode path; produces a `ConnectionStateView`
identical to the live session's final view (FR-019, SC-005).

**File location**: `python/minecraft_bot/wire_log.py`,
`rust/.../wire_log.rs`. JSONL spec lives in `contracts/wire-log-format.md`.

---

## E-9 `ReconnectPolicy`

**Purpose**: encapsulates the exponential-backoff parameters for
opt-in auto-reconnect (FR-007a).

**Fields**:
- `max_attempts: int = 5` — cap on retries before giving up and raising
- `initial_delay: float = 1.0` — seconds before first retry
- `max_delay: float = 30.0` — cap per-retry delay
- `multiplier: float = 2.0` — exponential factor
- `jitter: float = 0.25` — fractional random jitter applied to delays

**Validation**: `max_attempts >= 0`, `initial_delay > 0`, `max_delay >= initial_delay`,
`0 <= jitter < 1`.

**File location**: `python/minecraft_bot/connection.py` (small enough to
co-locate), `rust/.../connection.rs`.

---

## E-10 `ProtocolError` (typed error hierarchy)

**Purpose**: the surface error type for every disconnect or malformed-input
event (FR-007a).

**Hierarchy** (Python; Rust mirrors with `enum`):
```text
ProtocolError                # base
├── HandshakeFailed(reason)
├── LoginFailed(reason)
├── Disconnected             # clean server-initiated disconnect
│   └── KickedByServer(reason)
├── ConnectionDropped        # TCP-level loss
│   ├── KeepAliveTimeout
│   └── PeerReset
├── DecodeError              # malformed inbound packet
│   ├── UnknownPacketId(state, direction, id)
│   ├── OversizedVarInt(byte_count)
│   └── MalformedNbt(detail)
└── EncodeError              # cannot encode caller-provided value
    └── ValueOutOfRange(field, value)
```

**Validation**: every error carries a `__str__` /  `Display` impl that
includes the connection state and the packet id (where relevant).
Every error type is unit-tested with at least one constructor path.

**File location**: `python/minecraft_bot/errors.py`, `rust/.../errors.rs`.

---

## E-11 `RawPacket` (internal — not public)

**Purpose**: the framer's output before the registry decodes it. A
single hop in the decode pipeline (R-02, R-07).

**Fields**:
- `state: ConnectionState`
- `direction: Direction`
- `packet_id: int`
- `payload: bytes`

**Visibility**: internal. Public API exposes only the typed packet, not
this raw form.

**File location**: `python/minecraft_bot/_internal/decode_loop.py`,
`rust/.../framer.rs`.

---

## Cross-entity invariants

1. **Strict FIFO writes** (FR-013a): for any two `await connection.send(p1)`
   and `await connection.send(p2)` calls completing on the same
   `Connection` in any order across coroutines, the wire byte sequence is
   `encode(p1) ++ encode(p2)` if `await ... send(p1)` returned before
   `await ... send(p2)` was scheduled. Implementation: per-`Connection`
   `asyncio.Lock` around write+drain (R-03).

2. **State-respect** (FR-008): the registry refuses to decode a packet
   whose ID is not registered for the `Connection`'s current
   `ConnectionState`+`Direction`. Raising `UnknownPacketId` here is a
   bug and a test failure.

3. **Round-trip equality** (FR-013): for every packet class `P` and every
   value `v: P`, `decode(encode(v).bytes()) == v`. Tested via golden
   fixtures (E-5 Round-trip invariant).

4. **WireLog completeness** (FR-018): every successful decode and every
   successful encode emits exactly one `WireLogEntry` if the
   `Connection.wire_log` is set; failures emit a `WireLogEntry` with
   `fields=None` and the raw bytes preserved.

5. **Multi-bot readiness** (FR-017a): no entity above stores mutable state
   in module-global scope. The `CodecRegistry` is constructed once per
   process and is read-only after construction; safe to share across
   future `Connection` instances. `Connection` itself owns all per-session
   state.

6. **Auto-reconnect state discard** (FR-007a): after a reconnect cycle
   the `Connection`'s `_state_view` MUST be reset to its post-handshake
   initial values. Subscribers receive a `Reconnected` packet-shaped
   event; locally cached values become stale and the subscriber rebuilds
   them.

---

## Summary

11 entities. All trace back to a spec FR or constitution principle.
Hierarchy is shallow: a `Connection` owns a `WireLog` (optional), refers
to a shared `CodecRegistry`, holds a `ConnectionState`, and emits
`Packet` values whose schemas are encoded as files under
`protocol/v763/packets/`. Errors are typed and form a single hierarchy.
The Rust mirror is field-for-field identical (see `contracts/rust-api.md`).
