# Contract: Public API surface parity

**Feature**: 003-rust-pyo3-bridge
**Date**: 2026-05-12
**Status**: Authoritative — both backends MUST satisfy this contract

## Goal

Define the surface that `minecraft_bot_accel` MUST export so that
substituting `import minecraft_bot` with `import minecraft_bot_accel`
is a non-invasive code change (SC-007).

For each public symbol in `minecraft_bot`, this document lists the
corresponding symbol in `minecraft_bot_accel`. A parity test
(`tests/python/parity/test_api_surface.py`) introspects both modules
and fails the build if any symbol in the left column is missing or
has a divergent call signature.

## Top-level module: `Bot`

| Python (`minecraft_bot`) | Accel (`minecraft_bot_accel`) | Signature |
|---|---|---|
| `Bot.offline(host, port, username, *, wire_log=None)` | same | `(str, int, str, *, WireLog|None) -> Bot` |
| `Bot.connect()` | same | `async () -> None` |
| `Bot.disconnect(*, graceful=True)` | same | `async (*, bool) -> None` |
| `Bot.tick()` | same | `async () -> None` |
| `Bot.run()` | same | `async () -> None` (drives tick loop until disconnect) |
| `Bot.walk_to(x, y, z, *, max_fall=3, timeout=30.0)` | same | `async (float, float, float, *, int, float) -> bool` |
| `Bot.observation()` | same | `() -> Observation` |
| `Bot.use_item(hand=0)` | same | `async (int) -> None` |
| `Bot.drop_held_item(*, drop_stack=False)` | same | `async (*, bool) -> None` |
| `Bot.send(packet)` | same | `async (Packet) -> None` |
| `Bot.on_packet(name, fn)` | same | `(str, callable) -> Subscription` |
| `Bot.pre_tick(fn)` / `Bot.post_tick(fn)` | same | `(callable) -> Subscription` |
| `Bot.world` (property → `World`) | same | property |
| `Bot.position` / `health` / `food` / `yaw` / `pitch` / `on_ground` | same | float / int properties |
| `Bot.inventory` | same | property → `Inventory` |
| `Bot.effects` | same | property → `list[StatusEffect]` |

## World

| Python | Accel | Signature |
|---|---|---|
| `World.get_block(x, y, z)` | same | `(int, int, int) -> Block | None` |
| `World.get_block_id(x, y, z)` | same | `(int, int, int) -> int | None` |
| `World.find_blocks_nearby(center, radius, *, names=None, ids=None)` | same | `(Vec3 or tuple, int, *, list[str]|None, list[int]|None) -> list[Vec3]` |
| `World.get_chunk(cx, cz)` | same | `(int, int) -> Chunk | None` |
| `World.loaded_chunk_count()` | same | `() -> int` |

## Connection

| Python | Accel | Signature |
|---|---|---|
| `Connection.offline(host, port, username, *, wire_log=None)` | same | classmethod |
| `Connection.connect()` | same | `async () -> None` |
| `Connection.disconnect(*, graceful=True)` | same | `async (*, bool) -> None` |
| `Connection.send(packet)` | same | `async (Packet) -> None` |
| `Connection.state` | same | property → `ConnectionState` enum |
| `Connection.is_connected` | same | bool property |

## Codec primitives

| Python (`minecraft_bot.codec`) | Accel | Signature |
|---|---|---|
| `Reader(buf)` / `Writer()` | same | constructor |
| `varint.read(buf, offset)` | same | `(bytes, int) -> (int, int)` |
| `varint.write(value)` | same | `(int) -> bytes` |
| `varlong.read` / `varlong.write` | same | as above for i64 |
| `nbt.read(buf)` | same | `(bytes) -> (NbtTag, int)` |
| `nbt.write(tag)` | same | `(NbtTag) -> bytes` |
| `bitset.read` / `write` | same | per existing API |
| `slot.read` / `write` | same | per existing API |
| `chat_component.read` / `write` | same | per existing API |
| `identifier.read` / `write` | same | per existing API |
| `position.read` / `write` | same | per existing API |
| `string_codec.read` / `write` | same | per existing API |
| `uuid_codec.read` / `write` | same | per existing API |

## Framer

| Python (`minecraft_bot.framer`) | Accel | Signature |
|---|---|---|
| `Framer(compression_threshold=-1)` | same | constructor |
| `framer.encode_frame(payload)` | same | `(bytes) -> bytes` |
| `framer.decode_frame(buf, offset)` | same | `(bytes, int) -> (payload, total_consumed)` |
| `framer.set_compression(threshold)` | same | `(int) -> None` |

## Protocol packets

For every module under
`python/minecraft_bot/protocol/v763/packets/{state}/{direction}/`,
the accel namespace MUST expose a sibling module with:

- The packet dataclass type (e.g., `Position`, `KeepAlive`).
- `encode(pkt, writer)` and `decode(reader) -> pkt` functions.

A parity test enumerates the Python tree and asserts every module
exists in accel with matching `encode` / `decode` symbols and a
matching dataclass class.

## WireLog

| Python (`minecraft_bot.wire_log`) | Accel | Signature |
|---|---|---|
| `WireLog.to_jsonl(path)` | same | `(Path | str) -> WireLog` |
| `WireLog.append(direction, name, raw_bytes)` | same | `(str, str, bytes) -> None` |
| `WireLog.flush()` | same | `() -> None` |
| `WireLog.close()` | same | `() -> None` |

WireLog file format (JSONL) MUST be byte-identical between backends
(R-009). A roundtrip test:

```
1. Bot under backend A captures session_a.jsonl
2. Bot under backend B captures session_b.jsonl
3. diff session_a session_b → only timestamp deltas allowed
```

## Errors

The accel package MUST raise the same exception classes as Python by
name (caught with the same `except` clause). The accel package defines
its own exception classes in `minecraft_bot_accel.errors` matching
each Python class name and inheritance:

- `MinecraftBotError` (base)
- `ProtocolError(MinecraftBotError)`
- `DecodeError(ProtocolError)`
- `EncodeError(ProtocolError)`
- `OversizedVarInt(DecodeError)`
- `ConnectionError(MinecraftBotError)`
- `DisconnectedError(ConnectionError)`
- `KickError(ConnectionError)`
- `LoginError(ConnectionError)`
- `TimeoutError(ConnectionError)` — distinct from builtin

`isinstance(e, mb.ProtocolError)` and
`isinstance(e, mb_accel.ProtocolError)` are independent checks; user
code that catches both backends' exceptions catches by the appropriate
backend's class. Tests verify that catching the correct backend class
succeeds.

## Versioning attribute

`minecraft_bot_accel.__version__` — semver string.
`minecraft_bot_accel.python_compat` — the `minecraft_bot` line this
build claims parity with (e.g., `"0.2.x"`).
`minecraft_bot_accel.implementation` — the literal string `"rust"`
(distinct from `minecraft_bot.implementation == "python"`).
