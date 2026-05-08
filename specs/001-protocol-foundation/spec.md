# Feature Specification: Protocol Foundation

**Feature Branch**: `001-protocol-foundation`
**Created**: 2026-05-08
**Status**: Draft
**Input**: User description: "Minecraft wire protocol foundation: codecs, framer, packet registry, packet generator, handshake/login/status flow"

## Clarifications

### Session 2026-05-08

- Q: Multi-bot — in scope for this milestone or a later spec? → A: Single-connection is the functional scope; the architecture MUST keep multi-bot compatibility (no shared mutable globals; per-connection state; types crossing thread boundaries are `Send`/`Sync`-clean) so a later milestone can add N concurrent bots without refactoring `Connection`, codecs, or the registry.
- Q: Auto-reconnect on transient disconnect — built into `Connection` or developer-managed? → A: Hybrid, opt-in. By default (`auto_reconnect=False`) the framework MUST surface every unexpected disconnect as a typed error and MUST NOT retry. When the developer explicitly opts in (`auto_reconnect=True`), `Connection` MAY transparently re-establish the session using exponential backoff. Per-connection state (position, inventory, observed entities) is **always** discarded across sessions and rebuilt by the developer; auto-reconnect only re-runs the handshake on a fresh socket.
- Q: Decode-and-dispatch latency target (bytes-on-wire → typed value available to developer code) on commodity hardware? → A: Median ≤5 ms, p99 ≤25 ms — half of one server tick (50 ms / 20 TPS), so bots stay tick-aligned with the server.
- Q: Online-mode auth — how is it pre-wired in the API? → A: Separate factory constructors. This milestone ships `Connection.offline(host, port, username, ...)` only. A future milestone introduces `Connection.online_microsoft(...)` / `Connection.online_mojang(...)` without changing the offline factory. No `online=` boolean parameter is added to a shared constructor.
- Q: Packet ordering guarantee for serverbound packets on a single `Connection`? → A: Strict FIFO. The framework MUST serialize all serverbound writes from a single `Connection` so that packets appear on the wire in the order their `await send(...)` calls were issued, even when many coroutines (or many threads in Rust) hold a reference to the same `Connection`.

## User Scenarios & Testing *(mandatory)*

The "users" of this feature are developers who will build bots and AI agents on top of
the framework. Stakeholder language ("connect a bot", "see the world") is used; the
underlying wire protocol remains an implementation concern.

### User Story 1 - Connect a Bot to the Server and Reach Play State (Priority: P1)

A developer points the framework at the Paper 1.20.1 test server, supplies a player
name, and the framework completes the connection lifecycle on its own: it opens the
TCP socket, negotiates the protocol version, performs the offline-mode login
handshake, and announces that the bot has entered the Play state. From that moment the
bot stays alive on the server: it answers keep-alive pings, follows server-initiated
position synchronization, and remains visible in the player list until the developer
asks it to disconnect.

**Why this priority**: Without this story nothing else in the framework can be
exercised. Every other capability of the future Bot API (movement, inventory, combat,
observation) presupposes a live, healthy connection to a real server. This is the
"hello world" of the project.

**Independent Test**: A developer runs a 10-line script that constructs a bot,
connects, prints its initial position once Play state is entered, waits one minute,
and disconnects cleanly. The Paper server log shows the player joining, surviving for
60 seconds, and quitting without timeout.

**Acceptance Scenarios**:

1. **Given** an offline-mode Paper 1.20.1 server is reachable on the network, **When**
   a developer constructs a bot with the server address and a player name and asks it
   to connect, **Then** the framework completes the handshake/login flow and reports
   that Play state has been entered with a valid spawn position.
2. **Given** the bot is in Play state, **When** the server sends keep-alive requests,
   **Then** the framework answers each one within the protocol's timeout and the
   server does not drop the connection.
3. **Given** the bot is in Play state, **When** the server pushes a position
   synchronization, **Then** the framework records the new position and confirms it
   back to the server so the player is not bounced for "moved too quickly".
4. **Given** a bot is connected, **When** the developer asks it to disconnect, **Then**
   the framework closes the connection cleanly and the server log shows a normal
   disconnect, not a timeout.

---

### User Story 2 - Decode Every Server Message Without Unknown-Packet Errors (Priority: P1)

While a bot is connected the server continuously streams messages: chunk data, entity
spawns, chat, weather, time-of-day, advancements, recipe books, status effects, sound
events, and many more. Every message the server sends during a normal offline-mode
session must be recognized by the framework and surfaced as a typed value the
developer can inspect. There must be no "unknown packet id" exceptions and no silent
packet drops, even during the first chunk burst when dozens of message types arrive
within milliseconds.

**Why this priority**: A bot that ignores or crashes on unknown messages cannot
reliably observe the world. Read-side completeness (every server message is decoded)
is what makes the bot's view of the world trustworthy for downstream Bot API features
and for ML/LLM agents.

**Independent Test**: A developer connects a bot, waits 60 seconds in spectator
distance of a populated chunk, then captures and inspects the decoded packet trace.
Every received packet has a typed decoded form; no entries are tagged "unknown" or
"raw bytes only".

**Acceptance Scenarios**:

1. **Given** a bot has just entered Play state, **When** the server sends the initial
   chunk and entity bundle, **Then** every packet in that bundle is decoded into a
   typed value with no unknown-ID errors logged.
2. **Given** a bot is in Play state, **When** another player sends a chat message,
   **Then** the framework decodes the chat packet and the developer can read the
   sender, the message text, and the timestamp without parsing bytes by hand.
3. **Given** a bot is in Play state, **When** a mob spawns, takes damage, and dies,
   **Then** the framework decodes spawn, metadata, damage, and remove-entity packets
   in the correct order and the entity's tracked state matches the server's view.

---

### User Story 3 - Send Every Action a Bot Needs (Priority: P1)

The bot must be able to talk back. The framework exposes the full set of outgoing
messages required for offline-mode gameplay: client info on login, position and
look updates each tick, chat and command sending, slot selection, action clicks
(attack, use, hold-the-mouse-button-down windows), inventory manipulation,
teleport-confirm, plugin-channel responses, and disconnect. Every outgoing packet
that a higher-level Bot API will ever depend on is encodable today.

**Why this priority**: Without write-side completeness, bots can observe but not act —
half the framework. Encoding parity with the server's expectations is what separates a
chat-listener from a real bot.

**Independent Test**: A developer scripts a bot to chat "hello", swing its arm,
right-click the air, sneak for 1 second, change held slot to 5, and disconnect. Each
action appears in the Paper server's behaviour and logs in the expected order.

**Acceptance Scenarios**:

1. **Given** a bot is in Play state, **When** the developer asks it to send a chat
   message, **Then** the message appears in the server chat log within 200 ms and is
   visible to other connected players.
2. **Given** a bot is in Play state, **When** the developer issues a movement-update
   call with a target position, **Then** the framework emits the appropriate
   position+look packets and the server's reported player position matches within
   normal physics tolerance.
3. **Given** a bot is in Play state with a target block in reach, **When** the
   developer issues an attack action, **Then** the server registers the swing/attack
   on the targeted block or entity.

---

### User Story 4 - Inspect, Replay, and Diff the Wire (Priority: P2)

A developer can flip a switch and see every byte sent and received as a structured
log: timestamp, direction, state, packet name, decoded fields, raw payload. The same
log can be saved to disk and replayed offline to reconstruct the bot's state evolution
without re-connecting to a server. When a packet's wire format changes between
Minecraft versions, the developer can diff a single file to understand the change.

**Why this priority**: Long-running agent work fails in subtle ways. Replayable byte
logs are the difference between "we lost an hour repro-ing" and "we have the failing
session captured". This is also how new protocol versions get ported: byte logs from
the new version are diffed against schemas from the previous version.

**Independent Test**: A developer enables wire logging, connects a bot, has it walk
two blocks and chat once, disconnects, then runs an offline replay against the saved
log. The replay reconstructs the same final position, chat history, and inventory
without any network calls.

**Acceptance Scenarios**:

1. **Given** wire logging is enabled, **When** a bot session occurs, **Then** every
   packet in both directions is recorded with timestamp, direction, state, packet
   name, decoded fields, and full raw bytes.
2. **Given** a saved wire log from a previous session, **When** the developer runs
   the offline replay, **Then** the framework reproduces the bot's final position,
   inventory, and observed entities without connecting to any server.

---

### User Story 5 - Port a Single Packet to a New Protocol Version Without Touching Anything Else (Priority: P3)

When the framework eventually targets Minecraft 1.20.2 (protocol 764) or any later
version, porting a single packet — say, a tweak to the chat format — must require
editing exactly one file. Code that handles unrelated packets must not need changes.
Code that depends on the high-level Bot API must not need changes.

**Why this priority**: This is the long-term maintainability bet. It does not need to
ship in the first milestone (only protocol 763 is in scope), but the structure that
makes it possible must already be in place from day one — otherwise the rewrite to
get it later is much larger.

**Independent Test**: A developer creates an empty `protocol/v764/` folder, copies one
packet's file from `v763/` into it with a single field renamed, and the test suite
proves that protocol 763 still works unchanged while protocol 764 sees the new field
shape on that one packet.

**Acceptance Scenarios**:

1. **Given** the framework targets protocol 763, **When** the developer adds a
   `protocol/v764/` directory containing a single modified packet definition,
   **Then** the protocol 763 test suite continues to pass and the protocol 764 test
   suite picks up the modified packet without further code changes.

---

### Edge Cases

- **Compression threshold = -1 (disabled)**: server may run with compression off.
  All packets must remain decodable in this mode; the framer must not assume
  compression is active.
- **Compression threshold below packet size**: the framer must transparently switch
  between compressed and uncompressed packet headers based on the negotiated
  threshold. Packets smaller than the threshold travel uncompressed even when
  compression is enabled.
- **TCP fragmentation**: a single packet may arrive across several `recv` calls; the
  framer must accumulate bytes and only emit a packet when the full length-prefixed
  payload is present.
- **Oversized VarInt** (more than 5 bytes for VarInt, 10 for VarLong): treated as a
  malformed-input error that closes the connection rather than reading unbounded
  bytes.
- **Empty NBT compounds vs. absent NBT**: distinguish between a present-but-empty
  compound and an absent NBT field; both occur in 1.20.1 inventory slot data.
- **Server-initiated state transition mid-burst**: if the server moves the connection
  from Login to Play while packets are still buffered, the framer must continue
  decoding subsequent packets against the new state's registry.
- **Player position bounce ("moved too quickly")**: the framework's response to
  position-sync packets must not echo a position update back to the server — only
  the teleport-confirm — to avoid the prior incident captured in project memory.
- **Keep-alive timeout under load**: the framework must answer keep-alive pings
  even while it is busy processing a chunk burst, otherwise the server disconnects.
- **Connection lost mid-handshake**: surface a clean error to the developer
  instead of an opaque socket exception; the partially-initialized bot is
  discarded. With `auto_reconnect=False` (default) the framework does not
  retry — the developer constructs a new `Connection` to try again. With
  `auto_reconnect=True` the framework MAY restart the handshake on a new
  socket but MUST NOT carry any mid-handshake state forward.
- **Connecting twice with the same player name**: the second connection should
  receive a clean "already logged in" rejection from the server and surface it as
  a typed error.

## Requirements *(mandatory)*

### Functional Requirements

**Connection lifecycle**

- **FR-001**: The framework MUST establish a TCP connection to a Minecraft Java
  Edition server identified by host and port.
- **FR-002**: The framework MUST complete the protocol handshake by announcing
  protocol number 763 (Minecraft 1.20.1) and the requested next state (Status or
  Login).
- **FR-003**: The framework MUST complete the offline-mode login flow without
  requiring Microsoft/Mojang authentication and MUST transition the connection from
  Login to Play once the server signals login success.
- **FR-004**: The framework MUST honour a server-issued compression threshold,
  including the disabled value (-1), and MUST switch transparently between
  compressed and uncompressed packet headers based on per-packet payload size.
- **FR-005**: The framework MUST answer every server keep-alive request within the
  protocol's timeout window so the server does not disconnect the bot.
- **FR-006**: The framework MUST respond to server-initiated position
  synchronization with a teleport-confirm and MUST NOT echo a position-update
  packet in reply.
- **FR-007**: The framework MUST allow the developer to disconnect cleanly such
  that the server records a normal quit, not a timeout.
- **FR-007a**: The framework MUST surface every unexpected disconnect (TCP drop,
  keep-alive timeout, server-initiated kick, mid-handshake failure) as a typed
  error to the developer. Reconnect behaviour is opt-in via an explicit
  `auto_reconnect` option on `Connection`:
    - **Default (`auto_reconnect=False`)**: the framework MUST NOT retry. The
      caller receives the typed error and decides what to do.
    - **Opt-in (`auto_reconnect=True`)**: the framework MAY transparently
      re-run the full handshake on a new socket using exponential backoff;
      bounds for retry count and backoff MUST be configurable.
  In **both** modes per-connection state (position, inventory, observed
  entities, registries derived from login data) MUST be discarded between
  sessions; auto-reconnect re-establishes the wire only, never carries
  mid-session state forward.

**Read-side coverage**

- **FR-008**: The framework MUST decode every clientbound packet defined for
  protocol 763 across all relevant connection states (Handshaking, Status, Login,
  Play) without producing "unknown packet id" errors during a normal offline-mode
  session.
- **FR-009**: The framework MUST surface each decoded packet as a typed value with
  named fields, not as raw bytes, so developer code can read fields by name.
- **FR-010**: The framework MUST support all Minecraft primitive wire types used by
  protocol 763: variable-length integers and longs, length-prefixed UTF-8 strings,
  fixed-width integers and floats, booleans, UUIDs, packed block positions,
  identifiers, BitSets, NBT (compound, list, byte/int/long arrays, all primitive
  tags), inventory slots (item id + count + NBT), and chat components.
- **FR-011**: The framework MUST handle TCP fragmentation: a single packet may
  arrive across multiple read operations and MUST be reassembled before decoding.

**Write-side coverage**

- **FR-012**: The framework MUST encode every serverbound packet required for
  offline-mode gameplay across the Handshaking, Login, and Play states, sufficient
  to drive the future Bot API's movement, look, chat, command, action (attack/use),
  inventory click, slot selection, sneak, sprint, jump, and disconnect operations.
- **FR-013**: The framework MUST guarantee that any value encoded with its
  serializer can be decoded back to an equal value (round-trip correctness) for
  every supported primitive type and packet schema.
- **FR-013a**: The framework MUST serialize all serverbound writes from a
  single `Connection` so that packets appear on the wire in **strict FIFO
  order** matching the order in which `await connection.send(...)` calls were
  issued, regardless of how many coroutines (or threads, on the Rust side)
  hold a reference to the same `Connection`. This guarantee MUST hold across
  protocol-required ordering invariants (teleport-confirm before subsequent
  position updates, inventory click before reading the response, monotonic
  chat timestamps, etc.) without the developer having to add explicit locks.

**Architecture and portability**

- **FR-014**: Each packet definition MUST live in its own file at
  `{python|rust}/.../protocol/v763/packets/{state}/{direction}/{snake_case_name}.{py|rs}`.
- **FR-015**: Version-specific data tables (block states, registry IDs, particle
  codecs, entity metadata schemas) MUST be namespaced under the protocol number
  (`v763/`) the same way packets are.
- **FR-016**: Adding a new protocol version (e.g., `v764`) MUST be possible by
  creating a new sibling folder and replacing only the changed packets and tables;
  no edits to `v763/` MUST be required, and no edits outside the new folder MUST be
  required to keep the old version working.
- **FR-017**: A higher-level API surface defined at this milestone (Connection,
  ProtocolVersion, packet types, codec helpers) MUST be representable across the
  PyO3 boundary so a future Rust core can replace the Python implementation
  without changing the developer-facing Python API.
- **FR-017a**: Although this milestone scopes only **a single live `Connection`
  per process**, all framework state (`Connection`, codec registries, wire-log
  buffers, packet schemas) MUST be free of shared mutable globals and MUST
  satisfy thread-safety requirements (`Send`/`Sync` in Rust; per-connection
  isolation in Python) so that a future multi-bot milestone can run N
  concurrent connections in one process without refactoring `Connection`,
  codecs, or the registry.
- **FR-017b**: The connection-construction surface MUST be split by auth mode.
  This milestone exposes a single `Connection.offline(host, port, username,
  ...)` factory (and the equivalent Rust constructor). Online-mode auth is
  out of scope, but the API MUST reserve future factories
  (`Connection.online_microsoft`, `Connection.online_mojang`) such that
  adding them later does not change the offline factory's signature or
  semantics. No `online=` boolean parameter is permitted on a shared
  constructor.

**Observability and replay**

- **FR-018**: The framework MUST be able to log every inbound and outbound packet
  with timestamp, direction, connection state, packet name, decoded fields, and
  the raw bytes of the payload, under a single dedicated logger name.
- **FR-019**: A captured wire log MUST be replayable offline: feeding the log to
  the framework MUST reproduce the same final state evolution (position,
  inventory, observed entities, chat history) without making network calls.

**Quality**

- **FR-020**: Each supported primitive type and each packet schema MUST have a
  pure-byte test that encodes a known value, decodes the bytes back, and compares
  the result for equality.
- **FR-021**: A live-server smoke test MUST cover stories US1, US2, and US3
  end-to-end against the configured Paper 1.20.1 server and MUST pass before any
  change to codecs, framer, packet handlers, or the connection layer is merged.
- **FR-022**: When the live-server probe and a documentation source disagree on
  a numeric ID or schema detail, the live-server probe MUST be the authoritative
  value used in the framework.

### Key Entities

- **Connection**: a live link between the framework and a Minecraft server. Owns
  the network socket, current connection state (Handshaking / Status / Login / Play),
  the negotiated compression threshold, and the per-direction packet logs.
- **ProtocolVersion**: a numeric identifier (e.g., 763) that selects which packet
  schemas, registries, and data tables are in effect for a given Connection.
- **ConnectionState**: the discrete phase of the connection life cycle; controls
  which packet IDs are valid in each direction at any moment.
- **Packet**: a typed message exchanged in either direction with a name, a
  numeric ID for its current state, named fields, and a serialized byte form.
- **CodecRegistry**: the catalog mapping `(protocol_version, state, direction,
  packet_id)` to the packet schema responsible for decoding it, and mapping each
  packet name to its encoder.
- **WireLog**: a chronological record of packets observed on a Connection. May be
  written to a file, streamed to logging, or replayed offline.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can write a script of fewer than fifteen lines that
  connects a bot to the test server, prints its spawn position, waits one minute,
  and disconnects, with the server log showing a normal quit.
- **SC-002**: During a one-minute offline-mode session connecting to the test
  server with a populated spawn area, **100%** of received packets are decoded into
  typed values; zero "unknown packet id" log entries are produced.
- **SC-003**: A bot can stay continuously connected to the test server for at
  least **ten minutes** without any keep-alive timeout disconnect.
- **SC-004**: Every supported primitive Minecraft type (at minimum: VarInt,
  VarLong, String, UUID, Position, Identifier, BitSet, NBT, Slot, ChatComponent —
  no fewer than ten) passes a round-trip test for at least three distinct values
  including boundary cases.
- **SC-005**: A captured wire log replayed offline reproduces the same final
  reported position, inventory contents, and observed entity set as the live
  session that produced it.
- **SC-006**: Porting a single packet to a hypothetical protocol 764 by creating
  one new file under `protocol/v764/` and changing zero files elsewhere produces
  passing tests for both versions side by side.
- **SC-007**: Bringing a new developer up to "I have a bot in Play state on my
  own server" takes under **fifteen minutes** of reading and one server connection.
- **SC-008**: A live-server smoke test exercising all three P1 stories (connect,
  decode, send) completes in under **two minutes** wall-clock and is part of the
  default test command.
- **SC-009**: Decode-and-dispatch latency, measured from the moment a complete
  packet's bytes are read off the socket to the moment a typed decoded value
  is available to developer code, stays at **≤5 ms median** and **≤25 ms at
  the 99th percentile** under the test server's normal play stream
  (post-chunk-burst steady state) on commodity hardware (Ryzen 5 / Core i5
  class CPU). The framework MUST NOT introduce queueing depth that pushes
  p99 past this budget at steady-state load.

## Assumptions

- Initial scope is **protocol 763 only** (Minecraft 1.20.1). The directory layout
  is multi-version-ready, but no other protocol number is populated in this
  milestone.
- The default test target is the **Paper 1.20.1 server at `172.26.160.1:25565`**
  with `online-mode=false`. Other server software and online-mode are out of scope
  for this milestone.
- **Online-mode authentication** (Microsoft/Mojang sign-in, encryption handshake,
  session-server verification) is **out of scope** for this milestone. Architecture
  must not preclude it later, but no auth code ships here.
- The **higher-level Bot API** (pathfinding, A*, physics tick, automation
  helpers, behaviour trees, ML adapters) is **out of scope**. This milestone
  delivers only the protocol foundation those features will sit on top of.
- **Multi-bot** (running N concurrent connections in one process, a `BotPool`,
  cross-connection coordination) is **out of scope** for this milestone but the
  architecture is required to remain compatible with it (see FR-017a).
- The Python implementation lands first and is the reference; the Rust mirror
  follows under the cross-language parity rule. The PyO3 bridge is a later
  milestone, not this one.
- Authoritative protocol facts come from, in order: live-server probes against
  Paper 1.20.1, PrismarineJS `minecraft-data`, minecraft.wiki (the Wiki.vg merge),
  and other client/server sources as last-resort reference.
- The developer's environment can reach the test server on the network. The
  framework does not include server provisioning.
- Configuration state (introduced in protocol 764 / Minecraft 1.20.2) is **not
  present in protocol 763** and therefore not in scope; the state machine for this
  milestone is Handshaking → Status or Login → Play.
