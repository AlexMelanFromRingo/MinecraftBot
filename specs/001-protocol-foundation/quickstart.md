# Quickstart: Protocol Foundation

**Date**: 2026-05-08
**Plan**: [plan.md](./plan.md)
**Spec target**: SC-007 ("under 15 minutes to first Play state").

This document is the canonical "is the foundation working?" check. It
covers the three P1 user stories (US1 connect, US2 decode, US3 send) and
the P2 wire log (US4) in a copy-pasteable script.

---

## Prerequisites

1. **Test server running**. Paper 1.20.1 at `172.26.160.1:25565`,
   `online-mode=false`. Server folder on the Windows host:
   `C:\Users\Alex_Melan\Desktop\Minecraft-MC-Server`.
2. **Python 3.11+**. Verify: `python --version`.
3. **Rust stable** (only if exercising the Rust path). Verify:
   `rustc --version`.
4. From repo root, install editable Python package:
   ```bash
   pip install -e python/
   ```
5. (Rust path) From repo root:
   ```bash
   cargo build --manifest-path rust/Cargo.toml
   ```

---

## US1 — connect a bot, reach play, disconnect cleanly

### Python

```python
# tools/quickstart_us1.py
import asyncio
from minecraft_bot import Connection, V_1_20_1

async def main() -> None:
    async with Connection.offline(
        host="172.26.160.1",
        port=25565,
        username="QuickstartBot",
        version=V_1_20_1,
    ) as bot:
        await bot.connect()
        print("state =", bot.state)            # ConnectionState.PLAY
        print("compression threshold =", bot.compression_threshold)
        await asyncio.sleep(60)                 # stay alive 1 minute
        # disconnect handled by `async with` exit

asyncio.run(main())
```

Expected:
- Server console shows `QuickstartBot joined the game`.
- Script prints `state = ConnectionState.PLAY` and a non-negative compression threshold.
- After 60 s the script returns; server console shows
  `QuickstartBot left the game` (no "Disconnected: timeout").

This is the SC-001 / SC-007 acceptance test in script form.

### Rust

```rust
// rust/examples/quickstart_us1.rs
use minecraft_bot::{Connection, ConnectionOptions, V_1_20_1};
use std::time::Duration;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut bot = Connection::offline(
        "172.26.160.1",
        25565,
        "QuickstartBot",
        ConnectionOptions { version: V_1_20_1, ..Default::default() },
    ).await?;
    bot.connect().await?;
    println!("state = {:?}", bot.state());
    println!("compression threshold = {}", bot.compression_threshold());
    tokio::time::sleep(Duration::from_secs(60)).await;
    bot.disconnect(None).await?;
    Ok(())
}
```

Run: `cargo run --manifest-path rust/Cargo.toml --example quickstart_us1`.

---

## US2 — decode every packet from a populated chunk

```python
# tools/quickstart_us2.py
import asyncio, logging
from collections import Counter
from minecraft_bot import Connection, V_1_20_1, WireLog

logging.basicConfig(level=logging.INFO)

async def main() -> None:
    log = WireLog.in_memory()
    async with Connection.offline(
        host="172.26.160.1", port=25565, username="DecoderBot",
        version=V_1_20_1, wire_log=log,
    ) as bot:
        await bot.connect()
        await asyncio.sleep(60)

    counts = Counter(e.name for e in log.entries() if e.dir == "rx")
    print(f"Decoded {sum(counts.values())} clientbound packets across "
          f"{len(counts)} distinct types.")
    for name, n in counts.most_common(10):
        print(f"  {name}: {n}")

asyncio.run(main())
```

Expected:
- "Decoded N clientbound packets across M distinct types" with M ≥ 25
  for a populated spawn area.
- No `UnknownPacketId` entries in stderr (SC-002).

---

## US3 — send chat, swing arm, switch slot, disconnect

```python
# tools/quickstart_us3.py
import asyncio
from minecraft_bot import Connection, V_1_20_1
from minecraft_bot.protocol.v763.packets.play.serverbound.chat_message import ChatMessage
from minecraft_bot.protocol.v763.packets.play.serverbound.swing_arm import SwingArm, Hand
from minecraft_bot.protocol.v763.packets.play.serverbound.set_held_item import SetHeldItem

async def main() -> None:
    async with Connection.offline(
        host="172.26.160.1", port=25565, username="ActionBot",
        version=V_1_20_1,
    ) as bot:
        await bot.connect()
        await bot.send(ChatMessage(message="hello from ActionBot"))
        await bot.send(SwingArm(hand=Hand.MAIN_HAND))
        await bot.send(SetHeldItem(slot=5))
        await asyncio.sleep(2)

asyncio.run(main())
```

Expected:
- Chat appears in the server console within 200 ms.
- ActionBot's held slot changes to 5 (visible in player tab/inventory).
- Server log shows a normal disconnect.

---

## US4 — capture and replay

```python
# tools/quickstart_us4.py
import asyncio
from pathlib import Path
from minecraft_bot import Connection, V_1_20_1, WireLog

CAPTURE = Path("/tmp/qs.jsonl")

async def capture() -> None:
    async with Connection.offline(
        host="172.26.160.1", port=25565, username="CaptureBot",
        version=V_1_20_1, wire_log=WireLog.to_jsonl(CAPTURE),
    ) as bot:
        await bot.connect()
        await asyncio.sleep(30)

async def replay() -> None:
    rep = await WireLog.replay(CAPTURE, version=V_1_20_1)
    print("entries:", rep.entry_count)
    print("ended in state:", rep.state)

asyncio.run(capture())
asyncio.run(replay())
```

Expected:
- `/tmp/qs.jsonl` contains hundreds of lines, each a packet event.
- Replay completes without network access and prints the same final
  state the live session ended in (SC-005).

---

## Verification commands (full suite)

```bash
# Unit tests (no server needed)
pytest -q python/tests/unit

# Integration tests (server REQUIRED at 172.26.160.1:25565)
pytest -m live -q python/tests/integration

# Replay tests (no server needed; uses captured fixtures)
pytest -q python/tests/replay

# Performance budget (SC-009)
pytest -q --benchmark-only python/tests/perf

# Rust suites
cargo test --manifest-path rust/Cargo.toml
cargo test --manifest-path rust/Cargo.toml --features live-smoke

# Cross-language byte parity
python tools/cross_check.py
```

If everything is green, the foundation is healthy.

---

## Common failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| `ConnectionRefused` on `connect()` | Server not running, wrong host/port, or WSL2 NAT issues | Verify Paper console; check `netstat -an \| grep 25565` on Windows host |
| Hangs after `connect()` returns | `await connect()` returned before Play state was reached (bug) | Check `bot.state` before `sleep`; if it's `LOGIN`, see decode loop logs |
| `UnknownPacketId` in logs | Packet not yet implemented or registry override missing | Add packet file under `protocol/v763/packets/.../`; re-run |
| Server logs `moved too quickly` | Position-sync echo back to server (banned per FR-006) | Check for any code that emits a position update inside the sync handler |
| `KeepAliveTimeout` after long idle | Decode loop blocked by a slow user hook | Move slow work into `asyncio.create_task(...)` inside the hook |

---

## What's NOT covered here

- Online-mode auth (out of scope for this milestone).
- Pathfinding, physics, A*, automation (Bot API milestone).
- Multi-bot / `BotPool` (multi-bot milestone — architecture is ready,
  not yet exposed).
- ML / RL adapters (extras milestone).

If your task touches any of those, this milestone is the dependency,
not the destination.
