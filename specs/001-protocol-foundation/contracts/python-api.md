# Contract: Python Public API

**Date**: 2026-05-08
**Plan**: [../plan.md](../plan.md)

This is the **canonical, normative** contract for the Python public surface
of `minecraft_bot`. The Rust crate (`contracts/rust-api.md`) mirrors this
contract field-for-field and verb-for-verb.

Stability: every name in this file is part of the public API. Adding
fields/methods is a MINOR change; removing or renaming requires a MAJOR
version bump.

---

## Top-level imports

```python
from minecraft_bot import (
    Connection,
    ConnectionState,
    Direction,
    ProtocolVersion,
    V_1_20_1,
    ProtocolError,
    HandshakeFailed,
    LoginFailed,
    Disconnected,
    KickedByServer,
    ConnectionDropped,
    KeepAliveTimeout,
    PeerReset,
    DecodeError,
    UnknownPacketId,
    OversizedVarInt,
    MalformedNbt,
    EncodeError,
    ValueOutOfRange,
    ReconnectPolicy,
    WireLog,
    WireLogEntry,
    JsonlFile,
    LoggerSink,
    Tee,
    InMemory,
    Reconnected,        # event packet, fires after auto-reconnect cycle
)
```

Packet classes are imported from their module path:

```python
from minecraft_bot.protocol.v763.packets.play.clientbound.keep_alive import KeepAlive
from minecraft_bot.protocol.v763.packets.play.serverbound.chat_message import ChatMessage
```

---

## `Connection`

### Construction (factory only — FR-017b)

```python
@classmethod
def offline(
    cls,
    host: str,
    port: int,
    username: str,
    *,
    version: ProtocolVersion = V_1_20_1,
    auto_reconnect: bool = False,
    reconnect_policy: ReconnectPolicy | None = None,
    write_buffer_size: int = 1024,
    wire_log: WireLog | None = None,
) -> Connection: ...
```

Direct `Connection(...)` construction is **not** part of the public API.
Future milestones add `Connection.online_microsoft(...)` and
`Connection.online_mojang(...)` as siblings.

### Lifecycle

```python
async def connect(self) -> None:
    """Open TCP socket, run handshake → login → play. Raises HandshakeFailed
    or LoginFailed on protocol-level failure; ConnectionDropped on TCP loss
    before play state."""

async def disconnect(self, reason: str | None = None) -> None:
    """Send a clean disconnect, close the socket. Idempotent. Cancels the
    decode loop. After this, send() raises ConnectionClosed."""

async def __aenter__(self) -> Connection: ...
async def __aexit__(self, exc_type, exc, tb) -> None: ...
    # async with Connection.offline(...) as conn: ...
```

### State (read-only properties)

```python
@property
def state(self) -> ConnectionState: ...

@property
def version(self) -> ProtocolVersion: ...

@property
def host(self) -> str: ...

@property
def port(self) -> int: ...

@property
def username(self) -> str: ...

@property
def compression_threshold(self) -> int: ...
    # -1 if disabled

@property
def is_connected(self) -> bool: ...
```

### Sending packets — FIFO guaranteed (FR-013a)

```python
async def send(self, packet: ServerboundPacket) -> None:
    """Encode and write packet under the connection's FIFO write lock.
    Order of completion across coroutines maps directly to wire order.
    Raises ConnectionClosed if the connection is no longer open;
    EncodeError if the packet's fields are out of range."""
```

`ServerboundPacket` is a structural type alias (any frozen dataclass
under `protocol/v763/packets/{state}/serverbound/`). The framework
infers `state` and `id` from the packet's class.

### Receiving packets — hooks

```python
def on(self, packet_type: type[P], handler: Callable[[P], Awaitable[None] | None]) -> Subscription:
    """Subscribe to packets of a specific type. handler may be sync or async.
    Returns a Subscription whose .cancel() removes the handler.
    Handlers run inline in the decode loop's coroutine; spawn your own task
    for heavy work (see SC-009 latency budget)."""

def off(self, subscription: Subscription) -> None: ...

async def wait_for(
    self,
    packet_type: type[P],
    *,
    timeout: float | None = None,
    predicate: Callable[[P], bool] | None = None,
) -> P:
    """One-shot: returns the next packet matching type (and predicate, if
    given) or raises asyncio.TimeoutError after timeout."""
```

### Wire log integration

```python
@property
def wire_log(self) -> WireLog | None: ...

def attach_wire_log(self, log: WireLog) -> None: ...
    # mid-session attach allowed; logs from this point forward only
```

### Auto-reconnect events

When `auto_reconnect=True`, after a successful reconnect cycle the
`Connection` synthesizes a `Reconnected` event-packet that subscribers
can hook to rebuild local state.

```python
@dataclass(frozen=True, slots=True)
class Reconnected:
    attempts: int      # how many retries it took
    elapsed: float     # seconds the reconnect loop took
```

---

## Packet classes — shape contract

Every packet under `protocol/v763/packets/.../{name}.py` exposes:

```python
@dataclass(frozen=True, slots=True)
class PacketName:
    field_one: int
    field_two: str
    # ...

PACKET_ID: int = 0xNN
def decode(reader: Reader) -> PacketName: ...
def encode(packet: PacketName, writer: Writer) -> None: ...
```

- The `dataclass` is the public type and the round-trip subject.
- `PACKET_ID` is the numeric ID for the packet in its (state, direction).
- `decode`/`encode` are pure functions. They use `Reader`/`Writer` —
  thin byte-stream wrappers exposed in `minecraft_bot.codec` (see below).
- The packet's state and direction are implied by file path; the
  registry pairs them automatically.

**Round-trip invariant** (FR-013):

```python
encoded = bytes_writer()
encode(p, encoded)
assert decode(bytes_reader(encoded.bytes())) == p
```

---

## Codec primitives

```python
from minecraft_bot.codec import varint, varlong, string, uuid, position, identifier, bitset, nbt, slot, chat_component
```

Each codec module exposes:

```python
def read(reader: Reader) -> T: ...
def write(value: T, writer: Writer) -> None: ...
```

Supported `T` per codec is documented in `data-model.md` E-5.

`Reader` and `Writer` are simple byte-stream classes:

```python
class Reader:
    def __init__(self, data: bytes | bytearray): ...
    def read(self, n: int) -> bytes: ...
    def remaining(self) -> int: ...

class Writer:
    def __init__(self): ...
    def write(self, b: bytes) -> None: ...
    def bytes(self) -> bytes: ...
```

---

## `WireLog` contract

```python
class WireLog:
    def __init__(self, sink: WireLogSink): ...

    @classmethod
    def to_jsonl(cls, path: str | Path) -> WireLog: ...
    @classmethod
    def to_logger(cls, logger: logging.Logger) -> WireLog: ...
    @classmethod
    def in_memory(cls, capacity: int | None = None) -> WireLog: ...

    def entries(self) -> list[WireLogEntry]:
        """Available only for InMemory sinks; raises for streaming sinks."""

    @classmethod
    async def replay(cls, path: str | Path, *, version: ProtocolVersion = V_1_20_1) -> ReplayedConnection: ...
```

`ReplayedConnection` exposes the same read-only state surface as a live
`Connection` (everything except `send`, `disconnect`, `connect`).

---

## `ProtocolError` hierarchy

```python
class ProtocolError(Exception): ...
class HandshakeFailed(ProtocolError): ...
class LoginFailed(ProtocolError): ...
class Disconnected(ProtocolError): ...
class KickedByServer(Disconnected):
    def __init__(self, reason: str): ...
class ConnectionDropped(ProtocolError): ...
class KeepAliveTimeout(ConnectionDropped): ...
class PeerReset(ConnectionDropped): ...
class DecodeError(ProtocolError): ...
class UnknownPacketId(DecodeError):
    def __init__(self, state: ConnectionState, direction: Direction, id: int): ...
class OversizedVarInt(DecodeError):
    def __init__(self, byte_count: int): ...
class MalformedNbt(DecodeError):
    def __init__(self, detail: str): ...
class EncodeError(ProtocolError): ...
class ValueOutOfRange(EncodeError):
    def __init__(self, field: str, value): ...
class ConnectionClosed(ProtocolError): ...
```

---

## Logging contract

The framework logs under a single named logger:

```python
import logging
logging.getLogger("minecraft_bot.protocol").setLevel(logging.DEBUG)
```

Sub-loggers (informational only):
- `minecraft_bot.protocol.framer`
- `minecraft_bot.protocol.connection`
- `minecraft_bot.protocol.codec`

No log message is emitted from the public-API hot path above `INFO` level
unless `wire_log` is attached or the logger is explicitly set below
`WARNING`.

---

## Stability and evolution

- Adding a new optional keyword to `Connection.offline(...)` → MINOR
  (default-valued, additive).
- Adding a new packet under `protocol/v763/packets/.../` → MINOR
  (new file, doesn't change existing shapes).
- Adding `Connection.online_microsoft(...)` → MINOR (additive factory).
- Renaming any field on a packet, removing a typed error, or changing a
  `decode`/`encode` signature → MAJOR.
- Changing `WireLog` JSONL field names → MAJOR (replay format breaks).

The Rust crate (see `rust-api.md`) MUST track this contract within one
patch release; any divergence is a bug.
