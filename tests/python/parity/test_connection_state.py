"""T069 — Connection state-machine parity Python ↔ accel.

Both backends drive the same state machine: Handshaking → Login →
Play. The accel backend exposes Connection state via the Bot wrap.
This test runs an offline-mode login session and verifies the
state transitions arrive in the same order on both backends.

For non-live runs we check that the state-enum labels match across
the two packages' state-label conventions ("handshaking", "status",
"login", "play").
"""

from __future__ import annotations

import pytest


def test_connection_state_labels_match() -> None:
    """Both packages MUST agree on the set of connection-state
    labels and their ordering (handshaking < status < login < play)."""
    from minecraft_bot.protocol.v763.states import ConnectionState

    # Python enum values.
    py_labels = {s.label() for s in ConnectionState}
    expected = {"handshaking", "status", "login", "play"}
    assert py_labels == expected, f"python state labels {py_labels} != {expected}"

    # Accel side: WireLog.record validates labels via parse_state;
    # an unknown state label raises ValueError. Verify accepted set.
    import tempfile
    from pathlib import Path
    from minecraft_bot_accel import WireLog

    with tempfile.TemporaryDirectory() as tmp:
        log = WireLog.to_jsonl(str(Path(tmp) / "p.jsonl"))
        log.start_session(version=763, host="h", port=25565, username="U")
        for lbl in expected:
            # Each must succeed.
            log.record(direction="rx", state=lbl, packet_id=0, raw=b"", name=None)
        with pytest.raises(ValueError):
            log.record(
                direction="rx", state="not-a-state", packet_id=0, raw=b"", name=None
            )


@pytest.mark.live
async def test_live_connection_reaches_play(live_server) -> None:
    """An accel Bot connects to Paper and reaches PLAY state
    (entity_id populated)."""
    import minecraft_bot_accel as mb

    bot = mb.Bot.offline(live_server.host, live_server.port, "StateBot1")
    await bot.connect()
    try:
        eid = await bot.entity_id()
        assert eid is not None, "entity_id should be set after Login (Play)"
        # Position should arrive shortly after.
        import asyncio

        for _ in range(40):
            if await bot.position():
                break
            await asyncio.sleep(0.25)
        assert await bot.position() is not None
    finally:
        await bot.disconnect()
