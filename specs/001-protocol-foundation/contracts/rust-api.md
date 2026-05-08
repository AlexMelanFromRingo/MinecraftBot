# Contract: Rust Public API

**Date**: 2026-05-08
**Plan**: [../plan.md](../plan.md)
**Mirrors**: [python-api.md](./python-api.md) (canonical reference)

This is the **mirror** contract for the Rust crate `minecraft_bot`. Every
verb and field maps 1:1 to the Python contract. Where Rust idiom differs
(snake_case methods, `Result` returns, `enum` for typed errors), the
naming and semantic intent are preserved. Cross-language byte parity is
verified by `tools/cross_check.py` (R-08).

---

## Top-level imports

```rust
use minecraft_bot::{
    Connection,
    ConnectionState,
    Direction,
    ProtocolVersion,
    V_1_20_1,
    ProtocolError,
    ReconnectPolicy,
    WireLog,
    WireLogEntry,
    WireLogSink,
    Reconnected,
};
use minecraft_bot::protocol::v763::packets::play::clientbound::keep_alive::KeepAlive;
use minecraft_bot::protocol::v763::packets::play::serverbound::chat_message::ChatMessage;
```

---

## `Connection`

### Construction (factory only — FR-017b)

```rust
impl Connection {
    pub async fn offline(
        host: impl Into<String>,
        port: u16,
        username: impl Into<String>,
        opts: ConnectionOptions,
    ) -> Result<Self, ProtocolError>;
}

#[derive(Debug, Clone, Default)]
pub struct ConnectionOptions {
    pub version: ProtocolVersion,        // default: V_1_20_1
    pub auto_reconnect: bool,            // default: false
    pub reconnect_policy: Option<ReconnectPolicy>,
    pub write_buffer_size: usize,        // default: 1024
    pub wire_log: Option<WireLog>,
}
```

`Default::default()` for `ConnectionOptions` mirrors the Python kw-arg
defaults exactly. Direct `Connection::new` is **not** part of the public
API. Future milestones add `Connection::online_microsoft(...)` /
`Connection::online_mojang(...)`.

### Lifecycle

```rust
impl Connection {
    pub async fn connect(&mut self) -> Result<(), ProtocolError>;
    pub async fn disconnect(&mut self, reason: Option<String>) -> Result<(), ProtocolError>;
}
```

`Connection` is `Send + 'static` so `tokio::spawn` consumes it; this is
the multi-bot-readiness path (FR-017a).

### State (immutable getters)

```rust
impl Connection {
    pub fn state(&self) -> ConnectionState;
    pub fn version(&self) -> ProtocolVersion;
    pub fn host(&self) -> &str;
    pub fn port(&self) -> u16;
    pub fn username(&self) -> &str;
    pub fn compression_threshold(&self) -> i32;       // -1 if disabled
    pub fn is_connected(&self) -> bool;
}
```

### Sending packets — FIFO guaranteed (FR-013a)

```rust
impl Connection {
    pub async fn send<P: ServerboundPacket>(&self, packet: P) -> Result<(), ProtocolError>;
}
```

Internally guarded by `tokio::sync::Mutex<OwnedWriteHalf>` (R-03). The
`&self` (not `&mut self`) lets multiple tasks share an `Arc<Connection>`
and each call `send`; ordering follows lock-acquisition order.

`ServerboundPacket` is a trait implemented for every packet under
`protocol/v763/packets/.../serverbound/`:

```rust
pub trait ServerboundPacket: Send + Sync + 'static {
    const PACKET_ID: i32;
    const STATE: ConnectionState;
    fn encode(&self, writer: &mut dyn Writer) -> Result<(), ProtocolError>;
}

pub trait ClientboundPacket: Sized + Send + Sync + 'static {
    const PACKET_ID: i32;
    const STATE: ConnectionState;
    fn decode(reader: &mut dyn Reader) -> Result<Self, ProtocolError>;
}
```

### Receiving packets — hooks

```rust
impl Connection {
    pub fn on<P, F>(&mut self, handler: F) -> Subscription
    where
        P: ClientboundPacket + 'static,
        F: FnMut(&P) + Send + 'static;

    pub fn on_async<P, F, Fut>(&mut self, handler: F) -> Subscription
    where
        P: ClientboundPacket + 'static,
        F: FnMut(&P) -> Fut + Send + 'static,
        Fut: std::future::Future<Output = ()> + Send + 'static;

    pub fn off(&mut self, sub: Subscription);

    pub async fn wait_for<P>(
        &self,
        timeout: Option<std::time::Duration>,
        predicate: Option<Box<dyn Fn(&P) -> bool + Send>>,
    ) -> Result<P, ProtocolError>
    where
        P: ClientboundPacket + Clone + 'static;
}
```

Sync handlers run inline in the decode loop's task; spawn `tokio::spawn`
for heavy work (mirror of the Python latency advisory).

### Auto-reconnect events

```rust
#[derive(Debug, Clone, PartialEq)]
pub struct Reconnected {
    pub attempts: u32,
    pub elapsed: std::time::Duration,
}
```

When `auto_reconnect = true`, the `Connection` synthesises a `Reconnected`
clientbound-shaped event after a successful reconnect cycle.

---

## Packet shape contract

Every packet file under `rust/.../protocol/v763/packets/.../{name}.rs`:

```rust
use crate::codec::*;
use crate::errors::ProtocolError;
use crate::protocol::v763::states::{ConnectionState, Direction};

#[derive(Debug, Clone, PartialEq)]
pub struct PacketName {
    pub field_one: i32,
    pub field_two: String,
}

impl PacketName {
    pub const PACKET_ID: i32 = 0xNN;
    pub const STATE: ConnectionState = ConnectionState::Play;
    pub const DIRECTION: Direction = Direction::Clientbound;
}

impl ClientboundPacket for PacketName { /* ... */ }
// or: impl ServerboundPacket for PacketName { /* ... */ }
```

**Round-trip invariant** (FR-013): for every packet `p` of type `P`,
`P::decode(&mut Reader::from(P::encode(&p)?)) == Ok(p)`.

---

## Codec primitives

```rust
use minecraft_bot::codec::{varint, varlong, string, uuid, position, identifier, bitset, nbt, slot, chat_component};
```

Each module exposes:

```rust
pub fn read(reader: &mut dyn Reader) -> Result<T, ProtocolError>;
pub fn write(value: &T, writer: &mut dyn Writer) -> Result<(), ProtocolError>;
```

Types per codec match the table in `data-model.md` E-5 (e.g.,
`varint::T = i32`, `varlong::T = i64`, `nbt::T = NbtTag`, etc.).

`Reader` and `Writer` traits:

```rust
pub trait Reader: Send {
    fn read_exact(&mut self, n: usize) -> Result<&[u8], ProtocolError>;
    fn remaining(&self) -> usize;
}

pub trait Writer: Send {
    fn write_all(&mut self, b: &[u8]) -> Result<(), ProtocolError>;
}
```

A concrete `BytesReader<'a>` over `&[u8]` and a `BytesWriter` over
`Vec<u8>` are provided.

---

## `WireLog` contract

```rust
pub enum WireLogSink {
    InMemory { capacity: Option<usize> },
    JsonlFile(std::path::PathBuf),
    Logger(log::Logger),
    Tee(Vec<WireLogSink>),
}

impl WireLog {
    pub fn new(sink: WireLogSink) -> Self;
    pub fn to_jsonl(path: impl Into<std::path::PathBuf>) -> Self;
    pub fn to_logger(logger: log::Logger) -> Self;
    pub fn in_memory(capacity: Option<usize>) -> Self;

    pub fn entries(&self) -> Result<&[WireLogEntry], ProtocolError>; // InMemory only

    pub async fn replay(
        path: impl AsRef<std::path::Path>,
        version: ProtocolVersion,
    ) -> Result<ReplayedConnection, ProtocolError>;
}
```

The JSONL line format is the same as Python's (R-05) — bytes-level
identical files, replayable from either language.

---

## `ProtocolError` enum

```rust
#[derive(Debug, thiserror::Error)]
pub enum ProtocolError {
    #[error("handshake failed: {0}")]
    HandshakeFailed(String),
    #[error("login failed: {0}")]
    LoginFailed(String),
    #[error("disconnected: {0}")]
    Disconnected(String),
    #[error("kicked by server: {0}")]
    KickedByServer(String),
    #[error("connection dropped: {0}")]
    ConnectionDropped(String),
    #[error("keep-alive timeout")]
    KeepAliveTimeout,
    #[error("peer reset")]
    PeerReset,
    #[error("decode error: {0}")]
    DecodeError(String),
    #[error("unknown packet id: state={state:?} dir={direction:?} id={id}")]
    UnknownPacketId { state: ConnectionState, direction: Direction, id: i32 },
    #[error("oversized varint ({byte_count} bytes)")]
    OversizedVarInt { byte_count: usize },
    #[error("malformed NBT: {0}")]
    MalformedNbt(String),
    #[error("encode error: {0}")]
    EncodeError(String),
    #[error("value out of range: field={field} value={value}")]
    ValueOutOfRange { field: String, value: String },
    #[error("connection closed")]
    ConnectionClosed,
    #[error("io error: {0}")]
    Io(#[from] std::io::Error),
}
```

Variants line up 1:1 with the Python class hierarchy in `python-api.md`,
which is the normative reference if a question of "is this the same
error?" arises.

---

## Logging contract

The crate emits records under target `minecraft_bot::protocol`. The
exact target string mirrors the Python logger name (with `::` instead of
`.`).

```rust
log::set_max_level(log::LevelFilter::Debug);
```

---

## Stability and evolution

Tracking the Python contract:
- New `ConnectionOptions` field with `Default` impl → MINOR.
- New packet file → MINOR.
- New variant on `ProtocolError` → MINOR (since the enum is `#[non_exhaustive]`).
- Renaming any public type, removing an enum variant, or changing a trait
  bound → MAJOR.

Drift between Python and Rust contracts is a bug. The cross-language
parity check (`tools/cross_check.py`, R-08) is the enforcement.
