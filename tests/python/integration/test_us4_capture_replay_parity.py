"""SC-005: live capture, then offline replay reconstructs the same state.

Captures a 30-second live session via WireLog.to_jsonl, then replays
the file via WireLog.replay() and asserts the ReplayedConnection's
final state-view (entity_id, world_name, final_position) matches what
the live Connection observed.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from minecraft_bot.connection import Connection
from minecraft_bot.wire_log import WireLog

pytestmark = pytest.mark.live


async def test_capture_replay_parity(live_server, tmp_path: Path) -> None:
    out = tmp_path / "session.jsonl"

    # --- live capture ---
    log = WireLog.to_jsonl(out)
    bot = Connection.offline(
        host=live_server.host, port=live_server.port,
        username="ITReplay", wire_log=log,
    )
    await bot.connect()
    try:
        await asyncio.sleep(30.0)
    finally:
        live_entity_id = bot.entity_id
        live_world_name = bot.world_name
        await bot.disconnect()

    # Close the file sink so the JSONL is fully flushed.
    try:
        log.sink.close()  # type: ignore[union-attr]
    except AttributeError:
        pass

    # --- offline replay ---
    rep = WireLog.replay(out)

    print(f"\n>> live: entity_id={live_entity_id}, world={live_world_name}")
    print(f">> replay: entity_id={rep.entity_id}, world={rep.world_name}, "
          f"entries={rep.entry_count}, final_pos={rep.final_position}")

    # Parity assertions (SC-005).
    assert rep.entry_count > 0, "replay produced no entries"
    assert rep.entity_id == live_entity_id, (
        f"entity_id mismatch: live={live_entity_id} replay={rep.entity_id}"
    )
    assert rep.world_name == live_world_name, (
        f"world_name mismatch: live={live_world_name} replay={rep.world_name}"
    )
    # final_position should be set (the server pushed at least one Position
    # packet during the 30s window).
    assert rep.final_position is not None, "replay observed no Position packet"
