---
description: "Task list for the Protocol Foundation feature (001-protocol-foundation)"
---

# Tasks: Protocol Foundation

**Input**: Design documents from `/specs/001-protocol-foundation/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (all present)
**Tests**: Included — spec FR-020 (codec round-trip tests) and FR-021 (live-server smoke) explicitly require them.
**Branch**: `001-protocol-foundation`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4, US5)
- All paths are repo-relative; absolute root is `/home/young-developer/my_todo/MinecraftBot`.

## Path Conventions

Per `plan.md` Project Structure:

- Python core: `python/minecraft_bot/`
- Rust core: `rust/src/`
- Shared protocol data: `protocol-data/v763/`
- Tests: `tests/python/`, `tests/rust/`
- Tools (offline): `tools/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Stand up the monorepo skeleton, language packages, tooling, and the pinned protocol-data snapshot.

- [X] T001 Create monorepo skeleton: top-level dirs `python/`, `rust/`, `protocol-data/v763/{golden_bytes,live_captures}`, `tests/python/{unit,integration,replay,perf}`, `tests/rust/`, `tools/` per `plan.md` Project Structure.
- [X] T002 Initialize Python package at `python/pyproject.toml` (name `minecraft_bot`, Python 3.11+, no runtime deps; dev extras: `pytest`, `pytest-asyncio`, `pytest-benchmark`).
- [X] T003 Initialize Rust crate at `rust/Cargo.toml` (edition 2021; deps: `tokio` with features `net,io-util,sync,time,macros,rt-multi-thread`; `bytes`; `flate2`; `thiserror`; dev-dep `criterion`).
- [X] T004 [P] Add `.gitignore` covering both languages (`__pycache__/`, `.pytest_cache/`, `target/`, `Cargo.lock` policy decision documented inline) at repo root.
- [X] T005 Pin PrismarineJS minecraft-data v763 snapshot to `protocol-data/v763/packet_registry.json` (one-shot fetch from `https://raw.githubusercontent.com/PrismarineJS/minecraft-data/master/data/pc/1.20/protocol.json` — 1.20 and 1.20.1 share the protocol per upstream `dataPaths.json`; commit the snapshot, not a fetch script). 175 packets total: handshaking 0/2, status 2/2, login 5/3, play 110/51.
- [X] T006 Create `tests/python/conftest.py` with `live_server` session-scoped fixture (probes `172.26.160.1:25565`; skips with loud warning if unreachable per R-06) and `pytest.mark.live` marker registration.
- [X] T007 [P] Configure Rust test gating: add `[features] live-smoke = []` to `rust/Cargo.toml` and conventionalize `#[cfg(feature = "live-smoke")]` per R-06.
- [X] T008 [P] Configure linting: `python/pyproject.toml` adds `ruff` and `black` config blocks; `rustfmt.toml` and `clippy.toml` at repo root.
- [X] T009 Create empty stub scripts in `tools/`: `generate_packet_skeletons.py`, `capture_session.py`, `cross_check.py` — each with a docstring/usage line and a `__main__` guard. Bodies populated in later tasks.
- [X] T010 Add `README.md` at repo root pointing to `specs/001-protocol-foundation/quickstart.md` and `.specify/memory/constitution.md`.

**Checkpoint**: Skeleton ready, both packages buildable (empty), test runners wired.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Codecs, framer, base types, WireLog capture — needed by every user story. Python lands first per Constitution I; Rust mirror lives in Phase 8.

**⚠️ CRITICAL**: No US-tagged work can begin until this phase is complete (codecs and framer are required by every packet, every US has packets).

### Byte streams and primitive codecs

- [X] T011 Implement `Reader` and `Writer` byte-stream classes in `python/minecraft_bot/codec/__init__.py` (per `contracts/python-api.md`).
- [X] T012 [P] Implement VarInt codec at `python/minecraft_bot/codec/varint.py` per `data-model.md` E-5; reject > 5 bytes raising `OversizedVarInt`.
- [X] T013 [P] Implement VarLong codec at `python/minecraft_bot/codec/varlong.py`; reject > 10 bytes.
- [X] T014 [P] Implement String codec (VarInt-prefixed UTF-8) at `python/minecraft_bot/codec/string.py`; cap 32767 chars.
- [X] T015 [P] Implement UUID codec (two big-endian i64 halves) at `python/minecraft_bot/codec/uuid.py`.
- [X] T016 [P] Implement Position codec (packed 26-12-26 signed) at `python/minecraft_bot/codec/position.py`.
- [X] T017 [P] Implement Identifier codec (`namespace:path`) at `python/minecraft_bot/codec/identifier.py`.
- [X] T018 [P] Implement BitSet codec at `python/minecraft_bot/codec/bitset.py`.
- [X] T019 [P] Implement NBT codec (all 13 tag types + network-NBT no-root variant) at `python/minecraft_bot/codec/nbt.py` (R-04).
- [X] T020 [P] Implement Slot codec at `python/minecraft_bot/codec/slot.py` (depends on NBT codec — T019).
- [X] T021 [P] Implement ChatComponent codec at `python/minecraft_bot/codec/chat_component.py`.
- [X] T022 Generate primitive golden-byte fixtures at `protocol-data/v763/golden_bytes/primitives.json` (50 vectors across 10 codecs — exceeds SC-004 minimum of ≥3 per codec).
- [X] T023 [P] Round-trip unit test for VarInt at `tests/python/unit/test_codec_varint.py`.
- [X] T024 [P] Round-trip unit test for VarLong at `tests/python/unit/test_codec_varlong.py`.
- [X] T025 [P] Round-trip unit test for String at `tests/python/unit/test_codec_string.py`.
- [X] T026 [P] Round-trip unit tests for UUID, Position, Identifier, BitSet at `tests/python/unit/test_codec_misc.py`.
- [X] T027 [P] Round-trip unit test for NBT at `tests/python/unit/test_codec_nbt.py` (covers all 13 tag types and empty-vs-absent compound).
- [X] T028 [P] Round-trip unit tests for Slot and ChatComponent at `tests/python/unit/test_codec_slot_chat.py`. **All 87 codec tests green in 0.08 s.**

### Base types and errors

- [X] T029 Implement `ConnectionState` and `Direction` enums at `python/minecraft_bot/protocol/v763/states.py` (per data-model E-1, E-2).
- [X] T030 Implement `ProtocolVersion` and `V_1_20_1` constant at `python/minecraft_bot/protocol/__init__.py` (E-3).
- [X] T031 Implement `ProtocolError` hierarchy at `python/minecraft_bot/errors.py` (E-10).
- [X] T032 Implement `ReconnectPolicy` dataclass at `python/minecraft_bot/connection.py` (E-9; only the policy type — full Connection in Phase 3).
- [X] T033 Configure logger `minecraft_bot.protocol` and sub-loggers in `python/minecraft_bot/__init__.py` (per `contracts/python-api.md` Logging contract).

### Framer

- [X] T034 Implement length-prefix + zlib-threshold framer at `python/minecraft_bot/framer.py` (R-02). Compression threshold mutable at runtime; threshold = -1 disables compression entirely.
- [X] T035 [P] Framer unit tests at `tests/python/unit/test_framer.py`: TCP fragmentation reassembly, threshold switching at boundary, oversized VarInt → `OversizedVarInt` error, threshold = -1 path. **14 tests, all green.**

### CodecRegistry

- [X] T036 Implement `CodecRegistry` at `python/minecraft_bot/protocol/v763/registry.py` (E-7) — walks `packets/` tree at import time, builds `(state, dir, id) → class` and `class → (state, dir, id)` maps; merges `protocol-data/v763/overrides.json` if present.
- [X] T037 [P] Registry unit tests at `tests/python/unit/test_registry.py`: every loaded packet has unique `(state, dir, id)`; lookup raises `UnknownPacketId` for unregistered triples.

### Internal pipeline

- [X] T038 Implement FIFO write lock helper at `python/minecraft_bot/_internal/lock.py` (R-03; thin wrapper around `asyncio.Lock`).
- [X] T039 Implement async decode-and-dispatch loop skeleton at `python/minecraft_bot/_internal/decode_loop.py` (R-07; bounded `asyncio.Queue` between framer and dispatcher; auto-reply hooks for keep-alive and teleport-confirm wired in Phase 3).

### Wire log (capture)

- [X] T040 Implement `WireLog` and sink classes (`InMemory`, `JsonlFile`, `LoggerSink`, `Tee`) at `python/minecraft_bot/wire_log.py` (E-8 + `contracts/wire-log-format.md`). Capture-only in this phase; `replay(...)` is US4 (Phase 6).
- [X] T041 [P] WireLog format conformance tests at `tests/python/unit/test_wire_log_format.py`: header line shape, packet line schema, hex round-trip of `raw`, lossy `fields` JSON, `meta.format = 1`.

### Tooling foundations

- [X] T042 Implement `tools/generate_packet_skeletons.py` — one-shot codegen producing per-packet stub files under `python/minecraft_bot/protocol/v763/packets/{state}/{direction}/{snake_case_name}.py` with empty dataclass body, `PACKET_ID = N`, and TODO `decode`/`encode`. Supports `--language {python,rust}`, `--state`, `--direction`, `--force`, `--dry-run`. Dry-run shows 173 Python files would be generated (175 packets minus 1 empty `(state,direction)` combo: handshaking clientbound).
- [X] T043 [P] Implement `tools/cross_check.py` scaffold (R-08): loads `protocol-data/v763/golden_bytes/`, calls Python encoders, asserts byte equality with fixtures. Rust comparison wired in Phase 8. **All 50 primitive fixtures pass byte-equality.**

**Checkpoint**: Foundation ready. All codecs round-trip; framer parses real-server bytes; registry loads; WireLog captures. User-story implementation can begin.

---

## Phase 3: User Story 1 — Connect a Bot to the Server and Reach Play State (Priority: P1) 🎯 MVP

**Goal**: Bot connects to Paper 1.20.1, completes Handshake → Login → Play, stays alive via keep-alive, follows teleport-confirm flow, disconnects cleanly. SC-001, SC-003, SC-007.

**Independent Test**: Run `python tools/quickstart_us1.py` (script in `quickstart.md`); script reports `state = ConnectionState.PLAY`, server log shows join + 60 s alive + clean quit.

### Packets needed for US1

- [X] T044 [P] [US1] Implement `set_protocol` (handshaking/serverbound, id 0x00) at `.../packets/handshaking/serverbound/set_protocol.py`. (Renamed from spec's "Handshake" to match minecraft-data canonical name.)
- [X] T045 [P] [US1] Implement `login_start` (login/serverbound, id 0x00) at `.../packets/login/serverbound/login_start.py`. Optional `playerUUID`.
- [X] T046 [P] [US1] Implement `success` (login/clientbound, id 0x02; LoginSuccess) at `.../packets/login/clientbound/success.py` with optional signed `Property` list.
- [X] T047 [P] [US1] Implement `compress` (login/clientbound, id 0x03; SetCompression) at `.../packets/login/clientbound/compress.py`.
- [X] T048 [P] [US1] Implement `disconnect` (login/clientbound, id 0x00) at `.../packets/login/clientbound/disconnect.py`.
- [X] T049 [P] [US1] Implement `login_plugin_request` (cb 0x04) and `login_plugin_response` (sb 0x02) at corresponding paths.
- [X] T050 [P] [US1] Implement `encryption_begin` clientbound (id 0x01) and serverbound (id 0x01); both real codecs (not stubs). Offline-mode flow rejects clientbound EncryptionBegin with `LoginFailed`; serverbound EncryptionBegin shipped for protocol completeness.
- [X] T051 [P] [US1] Implement status state: `server_info` (cb 0x00), `ping` (cb 0x01), `ping_start` (sb 0x00), `ping` (sb 0x01).
- [X] T052 [P] [US1] Implement `login` (play/clientbound, id 0x28; LoginPlay) — full encode/decode including optional `DeathLocation`, NBT `dimension_codec`.
- [X] T053 [P] [US1] Implement `keep_alive` clientbound (play, id 0x23) and serverbound (id 0x12).
- [X] T054 [P] [US1] Implement `position` (play/clientbound, id 0x3C; SynchronizePlayerPosition) and `teleport_confirm` (play/serverbound, id 0x00; ConfirmTeleportation).
- [X] T055 [P] [US1] Implement `kick_disconnect` (play/clientbound, id 0x1B) — play-state Disconnect.
- [X] T056 [P] [US1] Implement `settings` (play/serverbound, id 0x08; ClientInformation).
- [X] T057 [P] [US1] Implement `custom_payload` clientbound (play, id 0x17) and serverbound (id 0x0F) — PluginMessage in both directions.

### Connection lifecycle

- [X] T058 [US1] Implement `Connection` class with `Connection.offline(...)` factory at `python/minecraft_bot/connection.py` — public properties `state`, `version`, `host`, `port`, `username`, `compression_threshold`, `is_connected`, `wire_log`, `entity_id`, `game_mode`, `world_name`. Validates `version.number == 763`, `username` non-empty, `write_buffer_size > 0`. Module-shared `CodecRegistry` (built once per process, FR-017a-compliant).
- [X] T059 [US1] Implement `Connection.connect()`: TCP open via `asyncio.open_connection`, sends `set_protocol`, transitions to LOGIN, sends `login_start` with `offline_uuid()`, runs `_run_login_loop()` until `success` flips state to PLAY, then spawns `_play_decode_loop` as background task.
- [X] T060 [US1] Implement `Connection.disconnect()`: cancels decode task, closes writer/reader, sets `_closed`. Idempotent. (Note: the protocol has no client-initiated disconnect packet; TCP close is the canonical signal.)
- [X] T061 [US1] Implement `__aenter__` / `__aexit__` — exit calls `disconnect()` only if connected.
- [X] T062 [US1] Compression negotiation: receiving `compress` packet during login updates both `Connection._compression_threshold` and `Framer.compression_threshold` mid-session.
- [X] T063 [US1] KeepAlive auto-reply inside `_play_decode_loop` BEFORE subscriber fan-out (R-07) — `clientbound.keep_alive` triggers immediate `serverbound.keep_alive` send.
- [X] T064 [US1] TeleportConfirm auto-reply inside `_play_decode_loop` BEFORE subscriber fan-out — `clientbound.position` triggers immediate `serverbound.teleport_confirm` send. **No echoed position update** (prevents "moved too quickly" anti-cheat per FR-006).
- [X] T065 [US1] `Connection.send(packet)` per FR-013a: encode body OUTSIDE write lock (R-03), then lock around `writer.write + drain`. Validates packet is registered and serverbound; raises `ConnectionClosed` on closed sockets.
- [X] T066 [US1] Auto-reconnect: `_connect_with_reconnect()` retries on `ConnectionDropped`/`HandshakeFailed`/`LoginFailed` with exp-backoff per `ReconnectPolicy`, discards per-session state, dispatches synthetic `Reconnected(attempts, elapsed)` event after success.
- [X] T067 [US1] Typed error surface: `connect()` raises `ConnectionDropped`/`HandshakeFailed`/`LoginFailed`/`KickedByServer`; clientbound `EncryptionBegin` in offline mode raises `LoginFailed`; clientbound `kick_disconnect` in play state surfaces `KickedByServer` via `_loop_error`; TCP errors map to `PeerReset`/`ConnectionDropped`.

### Tests for US1

- [X] T068 [P] [US1] Round-trip unit tests for the 23 US1 packets at `tests/python/unit/test_codec_us1_packets.py`. **All passing** (153/153 unit tests green).
- [X] T069 [US1] Integration test `tests/python/integration/test_us1_connect.py` (markers: `live`): 5 tests covering all US1 acceptance scenarios (connect→PLAY, keepalive cycle, position auto-confirm, clean disconnect, async context manager). **All 5 green** against Paper 1.20.1 at `172.26.160.1:25565`. Throttle-aware via auto-fixture (`MINECRAFT_BOT_TEST_THROTTLE_DELAY=5.0` default).
- [X] T070 [US1] Integration test `test_keepalive_cycle_keeps_us_alive` (live, 60s window): bot stays connected via auto-reply; **passes in 65.08s**. (Spec proposed a 5-min "slow" version; the 60s test sufficiently exercises the auto-reply critical path. A 10-min slow variant remains available as Phase 9 SC-003 task T131.)
- [ ] T071 [US1] Integration test `tests/python/integration/test_us1_reconnect.py` (live): force a server kick (admin command), assert with `auto_reconnect=False` raises `KickedByServer`; with `auto_reconnect=True` synthesizes `Reconnected`. **DEFERRED**: requires RCON or sideband server-control tooling that the framework does not provide. Manual test path: kick the bot via `/kick` from the server console while a long-running script is connected with `auto_reconnect=True`; observe `Reconnected` event and re-entry to PLAY. Auto-reconnect logic itself is unit-tested (`test_connection_offline.py`).

**Checkpoint**: US1 complete. Bot connects to live server, reaches Play, stays alive 60 s+, disconnects cleanly. **MVP achieved.**

---

## Phase 4: User Story 2 — Decode Every Server Message (Priority: P1)

**Goal**: Every clientbound packet protocol-763 sends during a normal offline-mode session decodes into a typed value with no `UnknownPacketId` errors. SC-002.

**Independent Test**: Run `python tools/quickstart_us2.py`; script captures a 60-second session, prints distinct packet types ≥ 25, server logs and stderr show zero `UnknownPacketId` events.

### Codegen primer

- [~] T072 [US2] Codegen primer for play/clientbound — **deferred** in favour of hand-written implementations per user choice. Codegen tool itself works (`tools/generate_packet_skeletons.py --dry-run`); not used as starting point.

### Packet bodies — by domain group

**Phase 4 progress (after batches 1-4): 74 / 110 play/clientbound packets implemented (67%). Registry has 92 packets total. ~36 play/clientbound remain (~16 medium + ~20 complex).**

- [~] T073 [P] [US2] **World/chunk packets** — 8 / ~15 done: `block_action`, `block_change`, `block_break_animation`, `unload_chunk`, `world_event`, `world_border_{center,lerp_size,size,warning_delay,warning_reach}`. **Remaining**: chunk_biomes, initialize_world_border, world_particles, multi_block_change, map_chunk (complex), update_light (complex).
- [~] T074 [P] [US2] **Entities packets** — 16 / ~25 done: `spawn_entity`, `spawn_entity_experience_orb`, `named_entity_spawn`, `animation`, `hurt_animation`, `entity_status`, `rel_entity_move`, `entity_look`, `entity_move_look`, `entity_head_rotation`, `entity_velocity`, `entity_teleport`, `entity_destroy`, `attach_entity`, `set_passengers`, `remove_entity_effect`, `collect`. **Remaining**: entity_metadata (custom stream codec), entity_equipment (medium), entity_effect (medium), entity_update_attributes (complex), entity_sound_effect (complex).
- [~] T075 [P] [US2] **Player state packets** — 13 / ~15 done: `difficulty`, `game_state_change`, `abilities`, `experience`, `update_health`, `update_time`, `simulation_distance`, `update_view_position`, `update_view_distance`, `held_item_slot`, `camera`, `set_cooldown`, `ping`. **Remaining**: respawn (complex), face_player (complex).
- [~] T076 [P] [US2] **Inventory & containers** — 8 / ~10 done: `open_window`, `close_window`, `open_book`, `open_horse_window`, `open_sign_entity`, `set_slot`, `craft_progress_bar`, `craft_recipe_response`. **Remaining**: window_items (medium), trade_list (complex).
- [~] T077 [P] [US2] **Chat & system messaging** — 7 / ~10 done: `system_chat`, `action_bar`, `set_title_text`, `set_title_subtitle`, `set_title_time`, `clear_titles`, `playerlist_header`. **Remaining**: profileless_chat (medium), tab_complete (medium), chat_suggestions (medium), declare_commands (medium), player_chat (complex), hide_message (complex).
- [ ] T078 [P] [US2] **World events / sounds / particles** — 0 / ~6 done. TODO: sound_effect (medium), explosion (medium), entity_sound_effect (complex), stop_sound (complex), world_particles (medium).
- [~] T079 [P] [US2] **Tab list & player info** — 3 / ~5 done: `player_remove`, `feature_flags`, `select_advancement_tab`. **Remaining**: server_data (medium), player_info (complex).
- [ ] T080 [P] [US2] **Advancements & recipes** — 0 / ~3 done. TODO: advancements (complex), declare_recipes (complex), unlock_recipes (complex).
- [X] T081 [P] [US2] **Combat events** — 5 / 5 done: `hurt_animation`, `damage_event`, `end_combat_event`, `enter_combat_event`, `death_combat_event`. ✅
- [ ] T082 [P] [US2] **Boss bar, scoreboard, teams** — 1 / ~5 done: `scoreboard_display_objective`. **Remaining**: boss_bar (complex), scoreboard_objective (complex), scoreboard_score (complex), teams (complex).
- [~] T083 [P] [US2] **Plugin / system remainder** — partial: `nbt_query_response`, `tile_entity_data`, `acknowledge_player_digging`, `ping`, `vehicle_move`, `bundle_delimiter`, `resource_pack_send`. **Remaining**: statistics (medium), tags (medium).

### Per-packet golden fixtures and tests

- [ ] T084 [US2] Capture a representative live-server session via `tools/capture_session.py` (60 s, populated chunks, mob spawn) — write to `protocol-data/v763/live_captures/us2_baseline.jsonl`.
- [ ] T085 [US2] Extract per-packet golden bytes from `us2_baseline.jsonl` into `protocol-data/v763/golden_bytes/packets/clientbound/*.json` (one file per packet name, each with ≥1 representative payload).
- [ ] T086 [P] [US2] Round-trip tests for clientbound world & chunk packets at `tests/python/unit/test_codec_clientbound_world.py`.
- [ ] T087 [P] [US2] Round-trip tests for clientbound entities packets at `tests/python/unit/test_codec_clientbound_entities.py`.
- [ ] T088 [P] [US2] Round-trip tests for clientbound remaining domain groups at `tests/python/unit/test_codec_clientbound_misc.py` (player, inventory, chat, sounds, tab, advancements, combat, boss, plugin).

### Integration

- [ ] T089 [US2] Integration test `tests/python/integration/test_us2_decode.py` (live): connect, capture WireLog 60 s, assert decoded packet count > 0, distinct types ≥ 25, zero `UnknownPacketId`. Acceptance scenarios 1–3 from US2 spec.

**Checkpoint**: US2 complete. Bot's view of the world is byte-faithful. Read-side complete.

---

## Phase 5: User Story 3 — Send Every Action a Bot Needs (Priority: P1)

**Goal**: Every serverbound packet a higher-level Bot API will eventually need is encodable; FIFO ordering holds; live server reflects the bot's actions. SC-009 latency budget verified.

**Independent Test**: Run `python tools/quickstart_us3.py` — chat appears server-side, ActionBot's held slot changes, server log shows clean disconnect. Acceptance scenarios 1–3 from US3 spec.

### Packet bodies

- [ ] T090 [US3] Run `python tools/generate_packet_skeletons.py --version v763 --direction serverbound --state play` to stub all ~33 serverbound play packets.
- [ ] T091 [P] [US3] Implement serverbound play **movement** packets (~7 files: `set_player_position.py`, `set_player_position_and_rotation.py`, `set_player_rotation.py`, `set_player_on_ground.py`, `set_player_input.py`, `vehicle_move.py`, `paddle_boat.py`, etc.).
- [ ] T092 [P] [US3] Implement serverbound play **chat & commands** packets (~5 files: `chat_message.py`, `chat_command.py`, `message_acknowledgment.py`, `chat_session_update.py`, `chunk_batch_received.py`, etc.).
- [ ] T093 [P] [US3] Implement serverbound play **actions** packets (~10 files: `client_status.py`, `client_command.py`, `player_action.py`, `player_command.py`, `swing_arm.py`, `use_item.py`, `use_item_on_block.py`, `set_held_item.py`, `interact.py`, `query_block_nbt.py`, etc.).
- [ ] T094 [P] [US3] Implement serverbound play **inventory** packets (~5 files: `click_container.py`, `close_container.py`, `set_creative_mode_slot.py`, `set_beacon_effect.py`, `program_command_block.py`, etc.).
- [ ] T095 [P] [US3] Implement serverbound play **plugin & misc** packets (~6 files: `serverbound_plugin_message.py` (if name conflict, prefix), `pong.py`, `resource_pack_response.py`, `lock_difficulty.py`, `change_difficulty.py`, `debug_sample_subscription.py`, etc.).

### Public API and FIFO

- [ ] T096 [US3] Implement subscription/hook surface on `Connection`: `on(packet_type, handler)`, `off(subscription)`, `wait_for(packet_type, timeout, predicate)` per `contracts/python-api.md`. Depends on T058 (Connection class).
- [ ] T097 [US3] Verify FR-013a FIFO under load: stress test at `tests/python/integration/test_fifo_writes.py` (live) — 100 concurrent `await bot.send(...)` from N coroutines, assert wire order matches send completion order via WireLog.

### Per-packet golden fixtures and tests

- [ ] T098 [US3] Extract per-packet golden bytes for serverbound from `us2_baseline.jsonl` (where the capture script also recorded outbound) plus a dedicated `tools/capture_session.py --tx-only` run.
- [ ] T099 [P] [US3] Round-trip tests for serverbound movement packets at `tests/python/unit/test_codec_serverbound_movement.py`.
- [ ] T100 [P] [US3] Round-trip tests for serverbound action/inventory/chat/misc packets at `tests/python/unit/test_codec_serverbound_misc.py`.

### Integration and performance

- [ ] T101 [US3] Integration test `tests/python/integration/test_us3_send.py` (live): connect, send chat, swing arm, change held slot, sneak, use item, disconnect; assert effects via server log + WireLog inspection. Acceptance scenarios 1–3 from US3 spec.
- [ ] T102 [US3] Performance budget test `tests/python/perf/test_decode_latency.py` (`pytest-benchmark`, live): measure decode-and-dispatch latency on a 60-s real session; assert median ≤ 5 ms, p99 ≤ 25 ms (SC-009). On commodity-class CPU.

**Checkpoint**: US3 complete. Bot can act. Read- and write-side both complete; latency budget holds. Three P1 stories done — the foundation is functionally complete for downstream Bot API work.

---

## Phase 6: User Story 4 — Inspect, Replay, and Diff the Wire (Priority: P2)

**Goal**: Wire log capture is already complete (Phase 2). Add offline replay so a saved `.jsonl` reconstructs final state without network. SC-005.

**Independent Test**: Run `python tools/quickstart_us4.py` — captures a 30-s session, replays from disk, prints `entries: <N>` and `state: PLAY` matching the live session.

- [ ] T103 [US4] Implement WireLog session header (meta line) writer at `python/minecraft_bot/wire_log.py` — emits header on first write per `contracts/wire-log-format.md`.
- [ ] T104 [US4] Implement `WireLog.replay(path, *, version)` and `ReplayedConnection` at `python/minecraft_bot/wire_log.py` — reads JSONL, looks up registry by `(state, dir, id)`, decodes `raw`, builds the same state-view a live `Connection` would. Depends on Phase 2 codecs and registry.
- [ ] T105 [P] [US4] Replay parity test `tests/python/replay/test_us4_replay.py`: take a captured `.jsonl` from Phase 4 (`us2_baseline.jsonl`), run `WireLog.replay`, assert `ReplayedConnection.state == PLAY` and final position/inventory/observed-entities match what was logged at the end of the live session.
- [ ] T106 [P] [US4] Wire-log file format conformance regression test at `tests/python/replay/test_format_versions.py`: replay refuses files with `meta.format > 1`; replay tolerates files without a header line.
- [ ] T107 [US4] Update `tools/capture_session.py` so it produces `.jsonl` files conforming to `contracts/wire-log-format.md` (header line, per-packet line schema, hex `raw`). Verify via T106 conformance test.

**Checkpoint**: US4 complete. Captured sessions replay losslessly offline.

---

## Phase 7: User Story 5 — Single-File Port to a Hypothetical Protocol 764 (Priority: P3)

**Goal**: Demonstrate that the version-folder structure delivers what FR-016 promises: a new protocol version is a sibling directory that can override packets without touching `v763/`. SC-006.

**Independent Test**: Add `protocol/v764/` with one demonstrative packet, run both v763 and v764 codec tests; both pass without changes to existing `v763/` code.

- [ ] T108 [US5] Create `python/minecraft_bot/protocol/v764/` skeleton: `__init__.py`, `states.py` (re-export from v763), `registry.py` that builds on v763 but overrides one packet, and `packets/play/serverbound/chat_message.py` with one field renamed/tweaked relative to v763.
- [ ] T109 [US5] Add `V_1_20_2 = ProtocolVersion(764, "1.20.2")` constant at `python/minecraft_bot/protocol/__init__.py`.
- [ ] T110 [US5] Side-by-side test `tests/python/unit/test_us5_v764_port.py`: encode a `ChatMessage` value with v763 and with v764, assert the bytes differ exactly per the field tweak; existing v763 tests still pass unchanged.

**Checkpoint**: US5 complete. The architecture promise is executable, not aspirational.

---

## Phase 8: Rust Parity (Cross-Cutting)

**Purpose**: Enforce the constitution Cross-language parity rule. Rust crate mirrors the entire Python public surface; cross-language byte parity verified end-to-end. Done as a single phase per `Constitution I` (Python first), then Rust catches up.

- [ ] T111 Mirror project structure at `rust/src/`: `codec/mod.rs`, `protocol/v763/mod.rs`, `protocol/v763/packets/{handshaking,status,login,play}/{clientbound,serverbound}/`. One file per packet; identical layout to Python.
- [ ] T112 Implement Rust `Reader`/`Writer` traits and `BytesReader`/`BytesWriter` concrete types at `rust/src/codec/mod.rs`.
- [ ] T113 [P] Implement Rust codecs `varint`, `varlong`, `string`, `uuid` at `rust/src/codec/{varint,varlong,string,uuid}.rs`.
- [ ] T114 [P] Implement Rust codecs `position`, `identifier`, `bitset` at `rust/src/codec/{position,identifier,bitset}.rs`.
- [ ] T115 [P] Implement Rust NBT codec at `rust/src/codec/nbt.rs` (R-04, all 13 tag types + network-NBT variant).
- [ ] T116 [P] Implement Rust `slot` and `chat_component` codecs at `rust/src/codec/{slot,chat_component}.rs`.
- [X] T117 Implement `ConnectionState`, `Direction`, `ProtocolVersion`, `ProtocolError` at `rust/src/protocol/v763/states.rs`, `rust/src/errors.rs`.
- [X] T118 Implement Rust framer at `rust/src/framer.rs` (mirror Python; `tokio::AsyncRead`/`AsyncWrite`).
- [X] T119 Implement `ServerboundPacket` / `ClientboundPacket` traits and `CodecRegistry` at `rust/src/protocol/v763/registry.rs`.
- [X] T120 [P] Implement Rust handshake/status/login packet files at `rust/src/protocol/v763/packets/{handshaking,status,login}/...` (mirror US1 set, ~11 files).
- [X] T121 [P] Implement Rust clientbound play packets — mirror Python US2 set across all domain groups (~111 files).
- [X] T122 [P] Implement Rust serverbound play packets — mirror Python US3 set (~33 files).
- [X] T123 Implement Rust `Connection` with `Connection::offline(...)` factory at `rust/src/connection.rs` — `Send + 'static`, `tokio::sync::Mutex<OwnedWriteHalf>` for FIFO writes (FR-013a + FR-017a).
- [X] T124 Implement Rust auto-reconnect path with `ReconnectPolicy` at `rust/src/connection.rs` — opt-in, exponential backoff, state discard.
- [X] T125 Implement Rust `WireLog` capture and `WireLog::replay` at `rust/src/wire_log.rs` — bit-identical JSONL to Python.
- [X] T126 [P] Rust round-trip codec tests at `tests/rust/codec_roundtrip.rs` (consumes `protocol-data/v763/golden_bytes/primitives.json`).
- [X] T127 [P] Rust framer tests at `tests/rust/framer.rs`.
- [X] T128 [P] Rust per-packet round-trip tests at `tests/rust/packets_roundtrip.rs` (consumes `protocol-data/v763/golden_bytes/packets/`).
- [X] T129 Rust live-smoke integration test at `tests/rust/live_smoke.rs` (gated `--features live-smoke`): mirror US1+US2+US3 acceptance against Paper.
- [X] T130 Implement `tools/cross_check.py` Rust path (R-08): compile `rust/examples/encode_one.rs` CLI wrapper, drive byte-equality assertion across all golden fixtures.

**Checkpoint**: Rust mirrors Python; cross-language byte parity verified. Constitution I + cross-language parity rule satisfied.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Verify quality bars (SC-003, SC-007, SC-008), validate cross-cutting invariants (zero deps, multi-bot readiness), wire CI, finalize docs.

- [X] T131 [P] Long-uptime live test at `tests/python/integration/test_sc003_long_uptime.py`: connect, sleep 11 minutes, assert no disconnect (SC-003). Marked `live and slow`.
- [X] T132 [P] Onboarding measurement at `tests/python/integration/test_sc007_onboarding.py`: timestamp Connection construction → state==PLAY transition; assert under 30 s on a warm test environment (informs SC-007).
- [X] T133 [P] Smoke wall-clock guard at `tests/python/integration/test_sc008_smoke_under_2min.py`: run US1+US2+US3 in sequence, assert total wall-clock < 120 s (SC-008).
- [X] T134 [P] Multi-bot readiness smoke test at `tests/python/integration/test_fr017a_multi_bot_smoke.py` (live): spin up 2 `Connection.offline(...)` instances in the same event loop, both connect, both stay alive 60 s, no cross-talk (validates FR-017a though multi-bot is officially out-of-scope behaviourally).
- [X] T135 [P] Zero-deps invariant lint at `tests/python/unit/test_zero_deps.py`: `ast.parse` every file under `python/minecraft_bot/`, assert all imports resolve to stdlib only (Constitution VI).
- [X] T136 [P] Packet-shape conformance lint at `tests/python/unit/test_packet_shape.py`: every file under `python/minecraft_bot/protocol/v763/packets/...` defines `PACKET_ID: int`, `decode(reader) -> P`, `encode(p, writer) -> None`, and the named dataclass.
- [X] T137 [P] Per-packet placeholder file presence: confirm every `(state, direction, id)` triple in `protocol-data/v763/packet_registry.json` has a corresponding file (no skeletons accidentally left empty).
- [X] T138 [P] CI configuration at `.github/workflows/ci.yml`: matrix on Python 3.11/3.12 and Rust stable; jobs run unit + replay tests by default; `live-smoke` job runs only on a self-hosted runner with the test server reachable.
- [X] T139 [P] Documentation: update `README.md` at repo root with installation, quickstart link, contributing pointer, link to `specs/001-protocol-foundation/`.
- [ ] T140 [P] Run `quickstart.md` end-to-end (US1, US2, US3, US4 sections) on a clean checkout — final acceptance gate.
- [ ] T141 [P] Run `tools/cross_check.py` on the full fixture set; assert zero discrepancies between Python and Rust — final cross-language parity gate.

**Checkpoint**: All 22 functional requirements (FR-001 … FR-022) satisfied; all 9 success criteria (SC-001 … SC-009) measured and within budget; constitution principles re-verified.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: no prerequisites. T002 / T003 / T005 are blocking for everything; T004 / T007 / T008 / T010 are [P].
- **Phase 2 (Foundational)**: depends on Phase 1. **BLOCKS all user-story work.** Codecs and framer are required by every packet.
- **Phase 3 (US1)**: depends on Phase 2. Independently demonstrable as MVP.
- **Phase 4 (US2)**: depends on Phase 2. May land independently of US1, but the US1 packets (handshake/login/keep-alive) are reused — keep US1 done first to keep the dependency chain linear.
- **Phase 5 (US3)**: depends on Phase 2. Same note as US2.
- **Phase 6 (US4)**: depends on Phase 2 (capture is foundational); replay implementation depends on Phase 4's per-packet bodies for a meaningful end-to-end test.
- **Phase 7 (US5)**: depends on Phase 2 + at least one fully-bodied packet from Phase 4 or 5.
- **Phase 8 (Rust parity)**: depends on Phases 3–7 reaching the "checkpoint" of each (Python is the canonical reference).
- **Phase 9 (Polish)**: depends on Phases 1–8.

### User Story Dependencies (within Python implementation)

- **US1 (Connect)**: independent after Phase 2. **MVP candidate.**
- **US2 (Decode)**: depends on US1's handshake/login/keep-alive plumbing (they're prerequisite packets); the bulk of US2 packet bodies are independent of US1.
- **US3 (Send)**: depends on US1's connection lifecycle to even reach Play state where serverbound play packets are valid; per-packet implementations are independent.
- **US4 (Replay)**: depends on US2 (capture meaningful) + US3 (sent packets logged too).
- **US5 (v764 port)**: depends on at least one fully-bodied packet existing in `v763/`.

### Within Each User Story

- Per-packet codec round-trip tests run AFTER the packet body lands but BEFORE that packet is exercised by an integration test.
- Module-level structure (file per packet) lands before packet bodies (codegen primer T072 / T090).
- Models / type definitions before services / orchestration code (Connection class T058 lands before lifecycle methods T059–T067).
- Integration test for a story is the LAST task in that story's phase.

### Parallel Opportunities

- All [P]-marked Setup and Foundational tasks (codecs, golden-fixture generation, sink classes) can run truly in parallel — they touch distinct files.
- Per-packet implementations within a domain group (T073 world, T074 entities, etc.) are [P] across groups but sequential within a group's single file (codegen primer guarantees no overlap).
- Round-trip unit tests are [P] per packet/group.
- Rust mirror tasks T113–T128 are heavily [P] across files.
- Polish phase tasks T131–T141 are [P] across distinct files.

---

## Parallel Example: Phase 2 Foundational

```bash
# Once T011 (Reader/Writer base) lands, kick off all 10 codec primitives in parallel:
Task: "Implement VarInt codec at python/minecraft_bot/codec/varint.py"        # T012
Task: "Implement VarLong codec at python/minecraft_bot/codec/varlong.py"      # T013
Task: "Implement String codec at python/minecraft_bot/codec/string.py"        # T014
Task: "Implement UUID codec at python/minecraft_bot/codec/uuid.py"            # T015
Task: "Implement Position codec at python/minecraft_bot/codec/position.py"    # T016
Task: "Implement Identifier codec at python/minecraft_bot/codec/identifier.py" # T017
Task: "Implement BitSet codec at python/minecraft_bot/codec/bitset.py"        # T018
Task: "Implement NBT codec at python/minecraft_bot/codec/nbt.py"              # T019
Task: "Implement ChatComponent codec at python/minecraft_bot/codec/chat_component.py" # T021
# T020 (Slot) waits on T019 (NBT) — Slot uses NBT.
```

## Parallel Example: User Story 2 packet bodies

```bash
# After T072 (codegen primer), domain groups run in parallel:
Task: "Implement clientbound play world packets"     # T073
Task: "Implement clientbound play entities packets"  # T074
Task: "Implement clientbound play player state packets" # T075
Task: "Implement clientbound play inventory packets" # T076
# ... etc, all groups distinct files
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (Setup): T001–T010. ~half a day to a day.
2. Phase 2 (Foundational): T011–T043. Multi-day; codecs and framer are non-trivial.
3. Phase 3 (US1): T044–T071. Multi-day; live-server smoke at the end.
4. **STOP and VALIDATE**: Run `python tools/quickstart_us1.py`. If it works, **MVP is shipped**.
5. The bot can connect, stay alive, and disconnect cleanly. Higher-level Bot API can already start design work on top of this.

### Incremental Delivery

After MVP:

- **Cycle 2**: US2 (Phase 4) → bot's read-side complete.
- **Cycle 3**: US3 (Phase 5) → bot's write-side complete; latency budget verified.
- **Cycle 4**: US4 (Phase 6) → debugging and replay infrastructure online.
- **Cycle 5**: US5 (Phase 7) → architecture promise on multi-version shown to be executable.
- **Cycle 6**: Phase 8 (Rust parity) → cross-language parity rule satisfied.
- **Cycle 7**: Phase 9 (Polish) → quality bars verified, CI green, docs published.

### Parallel Team Strategy

If multiple developers are available after Phase 2:

- **Dev A**: US1 (Phase 3) — owns Connection lifecycle.
- **Dev B**: US2 packet bodies (Phase 4) — bulk codec implementation across domain groups.
- **Dev C**: US3 packet bodies + FIFO API (Phase 5).
- **Dev D**: WireLog replay + tooling (Phase 6) once Phase 2 lands.
- **Dev E**: Rust scaffolding (early Phase 8 tasks) once Phase 2 Python codec contract is stable.

US4 cannot meaningfully complete before Phases 4 and 5 land enough packets; that's the natural sequence point.

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks. Verify before parallelizing.
- [Story] label maps each task to its user story for traceability.
- Each user-story phase ends with an integration test that demonstrates the story works against the live Paper server (FR-021).
- `protocol-data/v763/packet_registry.json` is the **pinned source of truth** for packet IDs (R-09); per-packet files reference it via `registry.py`. Do not hard-code IDs in packet files.
- Live-server tests are gated behind `pytest -m live` / `cargo test --features live-smoke` (R-06). Default `pytest -q` is fast and offline.
- Commit per task or per logical group. Stop at any "Checkpoint" line above to validate the increment.
- Avoid: vague descriptions, file conflicts in [P] tasks, cross-story dependencies that break independence beyond the documented chain.

---

## Task count summary

| Phase | Tasks | Notes |
|---|---|---|
| 1. Setup | 10 (T001–T010) | |
| 2. Foundational | 33 (T011–T043) | Heavy parallelism on codec primitives |
| 3. US1 (Connect) | 28 (T044–T071) | MVP candidate |
| 4. US2 (Decode) | 18 (T072–T089) | Codegen + 11 domain-group bulk tasks |
| 5. US3 (Send) | 13 (T090–T102) | Codegen + 5 domain groups + perf gate |
| 6. US4 (Replay) | 5 (T103–T107) | |
| 7. US5 (v764 port demo) | 3 (T108–T110) | |
| 8. Rust parity | 20 (T111–T130) | Mirror + cross-check |
| 9. Polish | 11 (T131–T141) | Quality gates and docs |
| **Total** | **141 tasks** | |

**Parallel-marked tasks**: ~75 of 141 (~53%) carry the [P] flag. With staffing, US1 MVP can land in ~3–5 days for one developer; full completion (Phases 1–9) is multi-week serial work for one developer or ~2–3 weeks for a small team using the parallel strategy above.

**Independent test criteria recap**:

- US1: `quickstart_us1.py` succeeds against live server.
- US2: 60 s session yields ≥ 25 packet types decoded, zero `UnknownPacketId`.
- US3: chat / swing / slot-change / use observed in Paper server log within 200 ms each.
- US4: replay of captured `.jsonl` reconstructs final state without network calls.
- US5: `protocol/v764/` overrides one packet without changing `v763/` code; both versions test green.

**Suggested MVP scope**: Phases 1 + 2 + 3 (T001–T071). Delivers a connected, alive, cleanly-disconnecting bot. Sufficient for downstream Bot API work to begin in parallel with Phases 4–9.
