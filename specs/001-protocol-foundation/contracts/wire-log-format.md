# Contract: Wire Log JSONL Format

**Date**: 2026-05-08
**Plan**: [../plan.md](../plan.md)
**Used by**: `WireLog` capture (`python-api.md`, `rust-api.md`) and offline
replay (FR-019, SC-005).

This is the **bytes-on-disk** contract for wire log files. Capture and
replay must be bit-identical across Python and Rust implementations.

---

## File format

- Encoding: UTF-8.
- Line ending: `\n` (LF). No trailing newline required.
- Each line is one well-formed JSON object. Lines are independently
  parseable (JSON Lines spec, https://jsonlines.org).
- File extension: `.jsonl`.
- No header, no footer, no comments. The first line MAY be a meta-line
  (see "Session header" below); replay tolerates both presence and
  absence.

---

## Session header (optional, line 1 only)

```json
{"meta": {"format": 1, "version": 763, "started_at": 1714867200.000000, "host": "172.26.160.1", "port": 25565, "username": "TestBot"}}
```

Fields:
- `meta.format` — schema version of *this format spec*. Must be `1` for
  this contract.
- `meta.version` — protocol number (763 for 1.20.1).
- `meta.started_at` — float seconds since Unix epoch.
- `meta.host`, `meta.port`, `meta.username` — purely informational.

If absent, replay infers protocol version from the first packet's
`(state, id)` pair when unambiguous; otherwise raises a
`MalformedReplay` error.

---

## Packet line schema

```json
{
  "ts": 0.001234,
  "dir": "rx",
  "state": "play",
  "id": 36,
  "name": "synchronize_player_position",
  "fields": {"x": 0.5, "y": 64.0, "z": 0.5, "yaw": 0.0, "pitch": 0.0, "flags": 0, "teleport_id": 1},
  "raw": "00000000000000003fe00000000000004050000000000000000000000000000000000001"
}
```

### Required fields

| Key | Type | Meaning |
|---|---|---|
| `ts` | `float` | Seconds elapsed since `meta.started_at`; if no header, raw `time.time()` value. Monotonic-aligned at session start so log line order is preserved on subsecond ties. |
| `dir` | `string` | One of `"rx"` (server → client, decoded) or `"tx"` (client → server, encoded). |
| `state` | `string` | One of `"handshaking"`, `"status"`, `"login"`, `"play"`. Lowercase. |
| `id` | `int` | The numeric packet ID in its `(state, direction)`. |
| `raw` | `string` | Lowercase hex-encoded raw payload bytes (the bytes that follow the packet-ID VarInt; **excludes** the length prefix and the packet-ID VarInt itself). This field is the **lossless source of truth** for replay. |

### Optional fields

| Key | Type | Meaning |
|---|---|---|
| `name` | `string` | snake_case packet name. Informational; replay does not depend on it. |
| `fields` | `object` | A best-effort JSON encoding of the decoded packet's fields, for human readability. **Lossy** for `bytes` and `NBT` fields (see "Lossy field encoding" below). Replay does not consume this. |

### Forbidden / reserved

- Any other top-level key MUST be ignored by replay (forward compatibility).
- A line whose JSON is malformed MUST cause replay to abort with a clear
  error pointing at the line number.

---

## Lossy field encoding (for `fields` only)

The `fields` object is for human inspection and grep. Any field type that
does not round-trip cleanly through JSON gets a noted approximation:

- `bytes` → hex string.
- NBT compound → nested JSON object; tag types are flattened (no
  preservation of byte/short/int/long distinction). Round-trip from
  `fields` alone is **not** supported.
- `f32` / `f64` → JSON number. Python's `repr()` round-trips both.
- `int64` exceeding `2^53-1` → string (e.g., `"9223372036854775807"`)
  to dodge the JS-number-precision pitfall.

The `raw` hex field is always present and authoritative; replay always
goes through `raw`.

---

## Replay semantics

`WireLog.replay(path)` constructs a `ReplayedConnection` whose final
state matches what the live `Connection` would have observed at the end
of the captured session (FR-019). Concretely:

1. Read the header (if present); set `protocol_version` accordingly.
2. For each line in order:
   - Hex-decode `raw` to bytes.
   - Look up the registry by `(state, "rx" → Clientbound | "tx" →
     Serverbound, id)`.
   - Call the packet's `decode` (or `encode` round-trip for `tx` lines —
     replay still feeds them to subscribers as if observed).
   - Update the `ReplayedConnection`'s state view exactly as the live
     decode loop would.
3. After the last line, the `ReplayedConnection` is returned to the
   caller for inspection.

Replay does NOT touch the network. Replay does NOT honour `ts` for
real-time pacing — it processes lines as fast as the host can.

---

## Capture semantics

The capturing `WireLog`:

- Writes the header line as the very first write before any packet lines.
- Writes one line per packet event, in the order the decode loop / send
  lock processes them.
- Flushes after every line for `JsonlFile` sinks (durability over
  throughput; capture is for debugging and tests, not high-rate prod).
- For `Tee` sinks, fans out to each child sink in order.
- For `LoggerSink`, emits one log record per line at `DEBUG` level under
  `minecraft_bot.protocol.wire`.
- For `InMemory` sinks, retains entries up to `capacity` (FIFO eviction
  if set; unbounded if `None`).

---

## Cross-language parity

A single `.jsonl` file produced by Python MUST replay identically in
Rust, and vice-versa. The acceptance test for SC-005 captures a session
with the Python client and replays it with the Rust client; the resulting
state views are compared field-by-field.

---

## Versioning of this format

`meta.format` is the format version. Any incompatible change (renamed
key, removed required field) requires a bump. Files with newer
`meta.format` than the reader supports MUST be rejected with a clear
"unsupported format version" error, not silently misread.

This milestone ships `meta.format = 1`.
